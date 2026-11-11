/*
 * metaltest: headless Metal self-test for the Redwood plug-in. Foundation + Metal + IOSurface only.
 *
 *   metaltest [--delay] [PATH-TO-default.metallib]
 *
 * Every line goes to stdout, which launchd points at /dev/console, the same channel the plug-in's
 * rw_print() uses (redwoodmetal.m), so the lines reach the kernel log. Format:
 *   METALTEST: NN name: PASS [detail] | FAIL reason | SKIP reason
 *   METALTEST: done P passed F failed S skipped
 * Each test runs under @try/@catch, a 10 s SIGALRM timeout and a crash-signal guard that
 * siglongjmp()s back to the runner. Exit status is always 0 (launchd must not respawn it).
 */
#import <Foundation/Foundation.h>
#import <IOSurface/IOSurfaceRef.h>
#import <Metal/Metal.h>
#import <setjmp.h>
#import <signal.h>
#import <stdarg.h>
#import <stdio.h>
#import <string.h>
#import <time.h>
#import <unistd.h>

enum { R_PASS, R_FAIL, R_SKIP };
#define W 64
#define H 64

static const char *kShaderSource =
	"#include <metal_stdlib>\n"
	"using namespace metal;\n"
	"struct VOut { float4 pos [[position]]; float2 uv; };\n"
	"vertex VOut vs_main(uint vid [[vertex_id]], constant float4 *v [[buffer(0)]], constant float &z [[buffer(1)]]) {\n"
	"  VOut o; o.pos = float4(v[vid].xy, z, 1.0); o.uv = v[vid].zw; return o; }\n"
	"fragment float4 fs_color(VOut in [[stage_in]], constant float4 &c [[buffer(0)]]) { return c; }\n"
	"fragment float4 fs_tex(VOut in [[stage_in]], texture2d<float> t [[texture(0)]]) {\n"
	"  constexpr sampler s(filter::nearest, address::clamp_to_edge); return t.sample(s, in.uv); }\n"
	"kernel void k_double(device uint *out [[buffer(0)]], uint i [[thread_position_in_grid]]) { out[i] = i * 2; }\n";

static id<MTLDevice> g_dev;
static id<MTLCommandQueue> g_q;
static id<MTLLibrary> g_srclib, g_binlib;
static const char *g_libpath = "/redwood/share/metaltest/default.metallib";
static char g_why[160];   // failure / skip reason of the running test
static char g_note[160];  // detail printed after PASS
static int g_pr;          // R_SKIP or R_FAIL, set when makePipe returns nil
static sigjmp_buf g_jmp;
static volatile sig_atomic_t g_sig;

static void
say(const char *fmt, ...)
{
	char line[190];
	va_list ap;
	va_start(ap, fmt);
	vsnprintf(line, sizeof(line), fmt, ap);
	va_end(ap);
	printf("METALTEST: %s\n", line);
	fflush(stdout);
}

static int
fail(const char *fmt, ...)
{
	va_list ap;
	va_start(ap, fmt);
	vsnprintf(g_why, sizeof(g_why), fmt, ap);
	va_end(ap);
	return R_FAIL;
}

static int
skip(const char *why)
{
	snprintf(g_why, sizeof(g_why), "%s", why);
	return R_SKIP;
}

static void
note(const char *fmt, ...)
{
	va_list ap;
	va_start(ap, fmt);
	vsnprintf(g_note, sizeof(g_note), fmt, ap);
	va_end(ap);
}

static const char *
errstr(NSError *e)
{
	return e ? [[e localizedDescription] UTF8String] : "(no NSError)";
}

static void
on_signal(int s)
{
	g_sig = s;
	siglongjmp(g_jmp, 1);
}

/* ---- helpers ---- */

static BOOL
finish(id<MTLCommandBuffer> cb, const char *what)
{
	[cb commit];
	[cb waitUntilCompleted];
	if ([cb status] != MTLCommandBufferStatusCompleted) {
		fail("%s: status %d error %s", what, (int)[cb status], errstr([cb error]));
		return NO;
	}
	return YES;
}

static id<MTLTexture>
newTex(MTLPixelFormat f, int w, int h, MTLTextureUsage u, MTLStorageMode sm, BOOL mips)
{
	MTLTextureDescriptor *d = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:f
		width:(NSUInteger)w height:(NSUInteger)h mipmapped:mips];
	d.usage = u;
	d.storageMode = sm;
	return [g_dev newTextureWithDescriptor:d];
}

static id<MTLTexture>
newTarget(void)
{
	return newTex(MTLPixelFormatBGRA8Unorm, W, H, MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead,
		MTLStorageModeShared, NO);
}

static void
readTex(id<MTLTexture> t, uint8_t *out, int w, int h)
{
	[t getBytes:out bytesPerRow:(NSUInteger)w * 4 fromRegion:MTLRegionMake2D(0, 0, (NSUInteger)w, (NSUInteger)h)
		mipmapLevel:0];
	(void)h;
}

static uint8_t
q8(float f)
{
	return (uint8_t)(f * 255.0f + 0.5f);
}

/* expected is RGBA float; pixels are BGRA8. Tolerance +-1 per channel. */
static BOOL
probe(const uint8_t *px, int w, int x, int y, float r, float g, float b, float a)
{
	const uint8_t *p = px + ((size_t)y * (size_t)w + (size_t)x) * 4;
	int want[4] = { q8(b), q8(g), q8(r), q8(a) };
	for (int i = 0; i < 4; i++) {
		int d = (int)p[i] - want[i];
		if (d < -1 || d > 1) {
			fail("px(%d,%d) BGRA got %u,%u,%u,%u want %d,%d,%d,%d", x, y, p[0], p[1], p[2], p[3],
				want[0], want[1], want[2], want[3]);
			return NO;
		}
	}
	return YES;
}

static id<MTLLibrary>
shaderLib(void)
{
	return g_binlib ? g_binlib : g_srclib;
}

typedef struct { float x, y, u, v; } Vtx;

static id<MTLRenderPipelineState>
makePipe(NSString *fsName, MTLPixelFormat depthFmt, BOOL blend)
{
	id<MTLLibrary> lib = shaderLib();
	if (!lib) {
		skip("no shader library (tests 06 and 07 both failed)");
		g_pr = R_SKIP;
		return nil;
	}
	id<MTLFunction> vs = [lib newFunctionWithName:@"vs_main"];
	id<MTLFunction> fs = [lib newFunctionWithName:fsName];
	if (!vs || !fs) {
		fail("newFunctionWithName nil (vs %s, fs %s)", vs ? "ok" : "nil", fs ? "ok" : "nil");
		g_pr = R_FAIL;
		return nil;
	}
	MTLRenderPipelineDescriptor *d = [[MTLRenderPipelineDescriptor alloc] init];
	d.vertexFunction = vs;
	d.fragmentFunction = fs;
	d.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
	d.depthAttachmentPixelFormat = depthFmt;
	if (blend) {
		d.colorAttachments[0].blendingEnabled = YES;
		d.colorAttachments[0].sourceRGBBlendFactor = MTLBlendFactorSourceAlpha;
		d.colorAttachments[0].destinationRGBBlendFactor = MTLBlendFactorOneMinusSourceAlpha;
		d.colorAttachments[0].sourceAlphaBlendFactor = MTLBlendFactorOne;
		d.colorAttachments[0].destinationAlphaBlendFactor = MTLBlendFactorOneMinusSourceAlpha;
	}
	NSError *e = nil;
	id<MTLRenderPipelineState> p = [g_dev newRenderPipelineStateWithDescriptor:d error:&e];
	if (!p) {
		fail("pipeline nil: %s", errstr(e));
		g_pr = R_FAIL;
	}
	return p;
}

static id<MTLRenderCommandEncoder>
beginPass(id<MTLCommandBuffer> cb, id<MTLTexture> c, MTLClearColor cc, id<MTLTexture> depth)
{
	MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
	rp.colorAttachments[0].texture = c;
	rp.colorAttachments[0].loadAction = MTLLoadActionClear;
	rp.colorAttachments[0].storeAction = MTLStoreActionStore;
	rp.colorAttachments[0].clearColor = cc;
	if (depth) {
		rp.depthAttachment.texture = depth;
		rp.depthAttachment.loadAction = MTLLoadActionClear;
		rp.depthAttachment.storeAction = MTLStoreActionDontCare;
		rp.depthAttachment.clearDepth = 1.0;
	}
	return [cb renderCommandEncoderWithDescriptor:rp];
}

/* one draw: vertex buffer(0) = verts, buffer(1) = z; fragment buffer(0) = colour (if non-NULL) */
static BOOL
draw(id<MTLRenderCommandEncoder> e, const Vtx *v, int n, MTLPrimitiveType t, const float *color, float z)
{
	id<MTLBuffer> vb = [g_dev newBufferWithBytes:v length:sizeof(Vtx) * (NSUInteger)n
		options:MTLResourceStorageModeShared];
	id<MTLBuffer> zb = [g_dev newBufferWithBytes:&z length:sizeof(z) options:MTLResourceStorageModeShared];
	id<MTLBuffer> cbuf = color ? [g_dev newBufferWithBytes:color length:16 options:MTLResourceStorageModeShared] : nil;
	if (!vb || !zb || (color && !cbuf)) {
		fail("newBufferWithBytes nil");
		return NO;
	}
	[e setVertexBuffer:vb offset:0 atIndex:0];
	[e setVertexBuffer:zb offset:0 atIndex:1];
	if (cbuf) {
		[e setFragmentBuffer:cbuf offset:0 atIndex:0];
	}
	[e drawPrimitives:t vertexStart:0 vertexCount:(NSUInteger)n];
	return YES;
}

static const Vtx kQuad[4] = { { -1, -1, 0, 1 }, { 1, -1, 1, 1 }, { -1, 1, 0, 0 }, { 1, 1, 1, 0 } };

/* ---- tests ---- */

static int
t01(void)
{
	g_dev = MTLCreateSystemDefaultDevice();
	if (!g_dev) {
		return fail("MTLCreateSystemDefaultDevice returned nil (is this process in sweetmetal_procs?)");
	}
	char fam[80] = "";
	for (int f = 1001; f <= 1005; f++) {
		size_t n = strlen(fam);
		snprintf(fam + n, sizeof(fam) - n, "%d=%d ", f, (int)[g_dev supportsFamily:(MTLGPUFamily)f]);
	}
	note("name=\"%.60s\" fam %s", [[g_dev name] UTF8String], fam);
	return R_PASS;
}

static int
t02(void)
{
	if (!g_dev) {
		return skip("no device");
	}
	g_q = [g_dev newCommandQueue];
	if (!g_q) {
		return fail("newCommandQueue nil");
	}
	id<MTLCommandBuffer> cb = [g_q commandBuffer];
	if (!cb) {
		return fail("commandBuffer nil");
	}
	return finish(cb, "empty cb") ? R_PASS : R_FAIL;
}

static int
t03(void)
{
	if (!g_dev) {
		return skip("no device");
	}
	id<MTLBuffer> b = [g_dev newBufferWithLength:256 options:MTLResourceStorageModeShared];
	if (!b) {
		return fail("newBufferWithLength nil");
	}
	uint32_t *p = [b contents];
	if (!p) {
		return fail("contents NULL");
	}
	for (uint32_t i = 0; i < 64; i++) {
		p[i] = i * 2654435761u;
	}
	const uint32_t *q = [b contents];
	for (uint32_t i = 0; i < 64; i++) {
		if (q[i] != i * 2654435761u) {
			return fail("word %u mismatch", i);
		}
	}
	if ([b length] < 256) {
		return fail("length %lu", (unsigned long)[b length]);
	}
	return R_PASS;
}

static int
t04(void)
{
	if (!g_dev) {
		return skip("no device");
	}
	id<MTLTexture> t = newTex(MTLPixelFormatBGRA8Unorm, W, H, MTLTextureUsageShaderRead, MTLStorageModeShared, NO);
	if (!t) {
		return fail("newTextureWithDescriptor nil");
	}
	static uint8_t in[W * H * 4], out[W * H * 4];
	for (int i = 0; i < W * H * 4; i++) {
		in[i] = (uint8_t)(i * 7 + (i >> 8));
	}
	[t replaceRegion:MTLRegionMake2D(0, 0, W, H) mipmapLevel:0 withBytes:in bytesPerRow:W * 4];
	readTex(t, out, W, H);
	if (memcmp(in, out, sizeof(in)) != 0) {
		for (int i = 0; i < W * H * 4; i++) {
			if (in[i] != out[i]) {
				return fail("byte %d: wrote %u read %u", i, in[i], out[i]);
			}
		}
	}
	return R_PASS;
}

static int
t05(void)
{
	if (!g_q) {
		return skip("no queue");
	}
	id<MTLTexture> t = newTarget();
	if (!t) {
		return fail("target nil");
	}
	id<MTLCommandBuffer> cb = [g_q commandBuffer];
	id<MTLRenderCommandEncoder> e = cb ? beginPass(cb, t, MTLClearColorMake(0.25, 0.5, 0.75, 1.0), nil) : nil;
	if (!e) {
		return fail("render encoder nil");
	}
	[e endEncoding];
	if (!finish(cb, "clear")) {
		return R_FAIL;
	}
	static uint8_t px[W * H * 4];
	readTex(t, px, W, H);
	for (int y = 0; y < H; y++) {
		for (int x = 0; x < W; x++) {
			if (!probe(px, W, x, y, 0.25f, 0.5f, 0.75f, 1.0f)) {
				return R_FAIL;
			}
		}
	}
	return R_PASS;
}

static int
t06(void)
{
	if (!g_dev) {
		return skip("no device");
	}
	NSError *e = nil;
	g_srclib = [g_dev newLibraryWithSource:[NSString stringWithUTF8String:kShaderSource] options:nil error:&e];
	if (!g_srclib) {
		return fail("newLibraryWithSource nil: %s", errstr(e));
	}
	return [g_srclib newFunctionWithName:@"vs_main"] ? R_PASS : fail("vs_main not found");
}

static int
t07(void)
{
	if (!g_dev) {
		return skip("no device");
	}
	NSError *e = nil;
	NSString *path = [NSString stringWithUTF8String:g_libpath];
	if (![[NSFileManager defaultManager] fileExistsAtPath:path]) {
		return fail("%s missing", g_libpath);
	}
	const char *how = "URL";
	g_binlib = [g_dev newLibraryWithURL:[NSURL fileURLWithPath:path] error:&e];
	if (!g_binlib) {
		char first[80];
		snprintf(first, sizeof(first), "%s", errstr(e));
		e = nil;
		how = "File";
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
		g_binlib = [g_dev newLibraryWithFile:path error:&e];
#pragma clang diagnostic pop
		if (!g_binlib) {
			return fail("URL: %s; File: %s", first, errstr(e));
		}
	}
	NSArray *names = [g_binlib functionNames];
	note("via %s, %lu functions", how, (unsigned long)[names count]);
	return [g_binlib newFunctionWithName:@"vs_main"] ? R_PASS : fail("vs_main not found in metallib");
}

static int
t08(void)
{
	if (!g_q) {
		return skip("no queue");
	}
	id<MTLRenderPipelineState> p = makePipe(@"fs_color", MTLPixelFormatInvalid, NO);
	if (!p) {
		return g_pr;
	}
	id<MTLTexture> t = newTarget();
	id<MTLCommandBuffer> cb = t ? [g_q commandBuffer] : nil;
	id<MTLRenderCommandEncoder> e = cb ? beginPass(cb, t, MTLClearColorMake(0, 0, 0, 1), nil) : nil;
	if (!e) {
		return fail("render encoder nil");
	}
	static const Vtx tri[3] = { { -1, -1, 0, 0 }, { 1, -1, 0, 0 }, { -1, 1, 0, 0 } };
	const float col[4] = { 1.0f, 0.5f, 0.25f, 1.0f };
	[e setRenderPipelineState:p];
	if (!draw(e, tri, 3, MTLPrimitiveTypeTriangle, col, 0.0f)) {
		return R_FAIL;
	}
	[e endEncoding];
	if (!finish(cb, "triangle")) {
		return R_FAIL;
	}
	static uint8_t px[W * H * 4];
	readTex(t, px, W, H);
	return (probe(px, W, 8, 56, 1, .5f, .25f, 1) && probe(px, W, 50, 58, 1, .5f, .25f, 1) &&
		probe(px, W, 56, 8, 0, 0, 0, 1) && probe(px, W, 58, 50, 0, 0, 0, 1)) ? R_PASS : R_FAIL;
}

static int
t09(void)
{
	if (!g_q) {
		return skip("no queue");
	}
	id<MTLRenderPipelineState> p = makePipe(@"fs_tex", MTLPixelFormatInvalid, NO);
	if (!p) {
		return g_pr;
	}
	id<MTLTexture> src = newTex(MTLPixelFormatBGRA8Unorm, 2, 2, MTLTextureUsageShaderRead, MTLStorageModeShared, NO);
	id<MTLTexture> t = newTarget();
	if (!src || !t) {
		return fail("texture nil");
	}
	/* BGRA bytes: (0,0) red, (1,0) green, (0,1) blue, (1,1) white */
	static const uint8_t texels[16] = { 0, 0, 255, 255, 0, 255, 0, 255, 255, 0, 0, 255, 255, 255, 255, 255 };
	[src replaceRegion:MTLRegionMake2D(0, 0, 2, 2) mipmapLevel:0 withBytes:texels bytesPerRow:8];
	id<MTLCommandBuffer> cb = [g_q commandBuffer];
	id<MTLRenderCommandEncoder> e = cb ? beginPass(cb, t, MTLClearColorMake(0, 0, 0, 1), nil) : nil;
	if (!e) {
		return fail("render encoder nil");
	}
	[e setRenderPipelineState:p];
	[e setFragmentTexture:src atIndex:0];
	if (!draw(e, kQuad, 4, MTLPrimitiveTypeTriangleStrip, NULL, 0.0f)) {
		return R_FAIL;
	}
	[e endEncoding];
	if (!finish(cb, "textured quad")) {
		return R_FAIL;
	}
	static uint8_t px[W * H * 4];
	readTex(t, px, W, H);
	return (probe(px, W, 16, 16, 1, 0, 0, 1) && probe(px, W, 48, 16, 0, 1, 0, 1) &&
		probe(px, W, 16, 48, 0, 0, 1, 1) && probe(px, W, 48, 48, 1, 1, 1, 1)) ? R_PASS : R_FAIL;
}

static int
t10(void)
{
	if (!g_q) {
		return skip("no queue");
	}
	id<MTLRenderPipelineState> p = makePipe(@"fs_color", MTLPixelFormatInvalid, YES);
	if (!p) {
		return g_pr;
	}
	id<MTLTexture> t = newTarget();
	id<MTLCommandBuffer> cb = t ? [g_q commandBuffer] : nil;
	id<MTLRenderCommandEncoder> e = cb ? beginPass(cb, t, MTLClearColorMake(0, 0, 1, 1), nil) : nil;
	if (!e) {
		return fail("render encoder nil");
	}
	const float col[4] = { 1, 0, 0, 0.5f };
	[e setRenderPipelineState:p];
	if (!draw(e, kQuad, 4, MTLPrimitiveTypeTriangleStrip, col, 0.0f)) {
		return R_FAIL;
	}
	[e endEncoding];
	if (!finish(cb, "blend")) {
		return R_FAIL;
	}
	static uint8_t px[W * H * 4];
	readTex(t, px, W, H);
	return probe(px, W, 32, 32, 0.5f, 0, 0.5f, 1) ? R_PASS : R_FAIL;
}

static int
t11(void)
{
	if (!g_q) {
		return skip("no queue");
	}
	id<MTLRenderPipelineState> p = makePipe(@"fs_color", MTLPixelFormatDepth32Float, NO);
	if (!p) {
		return g_pr;
	}
	MTLDepthStencilDescriptor *dd = [[MTLDepthStencilDescriptor alloc] init];
	dd.depthCompareFunction = MTLCompareFunctionLess;
	dd.depthWriteEnabled = YES;
	id<MTLDepthStencilState> ds = [g_dev newDepthStencilStateWithDescriptor:dd];
	id<MTLTexture> depth = newTex(MTLPixelFormatDepth32Float, W, H, MTLTextureUsageRenderTarget, MTLStorageModePrivate, NO);
	id<MTLTexture> t = newTarget();
	if (!ds || !depth || !t) {
		return fail("depth state/texture/target nil (state %s, depth %s)", ds ? "ok" : "nil", depth ? "ok" : "nil");
	}
	id<MTLCommandBuffer> cb = [g_q commandBuffer];
	id<MTLRenderCommandEncoder> e = cb ? beginPass(cb, t, MTLClearColorMake(0, 0, 0, 1), depth) : nil;
	if (!e) {
		return fail("render encoder nil");
	}
	const float red[4] = { 1, 0, 0, 1 }, green[4] = { 0, 1, 0, 1 };
	[e setRenderPipelineState:p];
	[e setDepthStencilState:ds];
	if (!draw(e, kQuad, 4, MTLPrimitiveTypeTriangleStrip, red, 0.3f) ||
		!draw(e, kQuad, 4, MTLPrimitiveTypeTriangleStrip, green, 0.6f)) {  /* farther: must be rejected */
		return R_FAIL;
	}
	[e endEncoding];
	if (!finish(cb, "depth")) {
		return R_FAIL;
	}
	static uint8_t px[W * H * 4];
	readTex(t, px, W, H);
	return probe(px, W, 32, 32, 1, 0, 0, 1) ? R_PASS : R_FAIL;
}

static int
t12(void)
{
	if (!g_q) {
		return skip("no queue");
	}
	id<MTLTexture> a = newTex(MTLPixelFormatBGRA8Unorm, 8, 8, MTLTextureUsageShaderRead, MTLStorageModeShared, NO);
	id<MTLTexture> b = newTex(MTLPixelFormatBGRA8Unorm, 8, 8, MTLTextureUsageShaderRead, MTLStorageModeShared, NO);
	if (!a || !b) {
		return fail("texture nil");
	}
	uint8_t in[8 * 8 * 4], out[8 * 8 * 4];
	for (int i = 0; i < 256; i++) {
		in[i] = (uint8_t)(i * 3 + 1);
	}
	[a replaceRegion:MTLRegionMake2D(0, 0, 8, 8) mipmapLevel:0 withBytes:in bytesPerRow:32];
	id<MTLCommandBuffer> cb = [g_q commandBuffer];
	id<MTLBlitCommandEncoder> e = [cb blitCommandEncoder];
	if (!e) {
		return fail("blitCommandEncoder returned nil");
	}
	[e copyFromTexture:a sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0, 0, 0) sourceSize:MTLSizeMake(8, 8, 1)
		toTexture:b destinationSlice:0 destinationLevel:0 destinationOrigin:MTLOriginMake(0, 0, 0)];
	[e endEncoding];
	if (!finish(cb, "blit copy")) {
		return R_FAIL;
	}
	readTex(b, out, 8, 8);
	return memcmp(in, out, sizeof(in)) == 0 ? R_PASS : fail("copied texture differs");
}

static int
t13(void)
{
	if (!g_q) {
		return skip("no queue");
	}
	id<MTLTexture> t = newTex(MTLPixelFormatBGRA8Unorm, 8, 8, MTLTextureUsageShaderRead, MTLStorageModeShared, YES);
	id<MTLBuffer> buf = [g_dev newBufferWithLength:8 * 8 * 4 options:MTLResourceStorageModeShared];
	if (!t || !buf) {
		return fail("texture/buffer nil");
	}
	uint8_t in[8 * 8 * 4];
	memset(in, 0x80, sizeof(in));
	[t replaceRegion:MTLRegionMake2D(0, 0, 8, 8) mipmapLevel:0 withBytes:in bytesPerRow:32];
	id<MTLCommandBuffer> cb = [g_q commandBuffer];
	id<MTLBlitCommandEncoder> e = [cb blitCommandEncoder];
	if (!e) {
		return fail("blitCommandEncoder returned nil");
	}
	[e generateMipmapsForTexture:t];
	[e copyFromTexture:t sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0, 0, 0) sourceSize:MTLSizeMake(8, 8, 1)
		toBuffer:buf destinationOffset:0 destinationBytesPerRow:32 destinationBytesPerImage:256];
	[e endEncoding];
	if (!finish(cb, "blit mips")) {
		return R_FAIL;
	}
	uint8_t top[4] = { 0 };
	[t getBytes:top bytesPerRow:4 fromRegion:MTLRegionMake2D(0, 0, 1, 1) mipmapLevel:3];
	const uint8_t *c = [buf contents];
	if (memcmp(c, in, sizeof(in)) != 0) {
		return fail("texture->buffer copy differs");
	}
	for (int i = 0; i < 4; i++) {
		if (top[i] < 0x7f || top[i] > 0x81) {
			return fail("mip 3 texel byte %d = %u, want 128", i, top[i]);
		}
	}
	return R_PASS;
}

static int
t14(void)
{
	if (!g_q) {
		return skip("no queue");
	}
	id<MTLLibrary> lib = shaderLib();
	if (!lib) {
		return skip("no shader library (tests 06 and 07 both failed)");
	}
	id<MTLFunction> f = [lib newFunctionWithName:@"k_double"];
	if (!f) {
		return fail("k_double not found");
	}
	NSError *e = nil;
	id<MTLComputePipelineState> ps = [g_dev newComputePipelineStateWithFunction:f error:&e];
	if (!ps) {
		return fail("compute pipeline nil: %s", errstr(e));
	}
	id<MTLBuffer> b = [g_dev newBufferWithLength:64 * 4 options:MTLResourceStorageModeShared];
	if (!b) {
		return fail("buffer nil");
	}
	memset([b contents], 0xEE, 64 * 4);
	id<MTLCommandBuffer> cb = [g_q commandBuffer];
	id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
	if (!ce) {
		return fail("computeCommandEncoder nil");
	}
	[ce setComputePipelineState:ps];
	[ce setBuffer:b offset:0 atIndex:0];
	[ce dispatchThreadgroups:MTLSizeMake(2, 1, 1) threadsPerThreadgroup:MTLSizeMake(32, 1, 1)];
	[ce endEncoding];
	if (!finish(cb, "compute")) {
		return R_FAIL;
	}
	const uint32_t *o = [b contents];
	for (uint32_t i = 0; i < 64; i++) {
		if (o[i] != i * 2) {
			return fail("out[%u] = %u want %u", i, o[i], i * 2);
		}
	}
	return R_PASS;
}

static int
t15(void)
{
	if (!g_q) {
		return skip("no queue");
	}
	NSDictionary *props = @{
		(id)kIOSurfaceWidth : @(W), (id)kIOSurfaceHeight : @(H), (id)kIOSurfaceBytesPerElement : @4,
		(id)kIOSurfaceBytesPerRow : @(W * 4), (id)kIOSurfacePixelFormat : @(0x42475241u) /* 'BGRA' */
	};
	IOSurfaceRef s = IOSurfaceCreate((__bridge CFDictionaryRef)props);
	if (!s) {
		return fail("IOSurfaceCreate nil");
	}
	MTLTextureDescriptor *d = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
		width:W height:H mipmapped:NO];
	d.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
	id<MTLTexture> t = [g_dev newTextureWithDescriptor:d iosurface:s plane:0];
	if (!t) {
		CFRelease(s);
		return fail("newTextureWithDescriptor:iosurface:plane: nil");
	}
	id<MTLCommandBuffer> cb = [g_q commandBuffer];
	id<MTLRenderCommandEncoder> e = cb ? beginPass(cb, t, MTLClearColorMake(0.5, 0.25, 1.0, 1.0), nil) : nil;
	if (!e) {
		CFRelease(s);
		return fail("render encoder nil");
	}
	[e endEncoding];
	int r = finish(cb, "iosurface clear") ? R_PASS : R_FAIL;
	if (r == R_PASS) {
		IOSurfaceLock(s, kIOSurfaceLockReadOnly, NULL);
		const uint8_t *base = IOSurfaceGetBaseAddress(s);
		size_t bpr = IOSurfaceGetBytesPerRow(s);
		if (!base) {
			r = fail("IOSurface base address NULL");
		} else {
			/* probe() wants a tight BGRA image: check a few texels with the surface's row pitch */
			static const int pts[4][2] = { { 0, 0 }, { 63, 0 }, { 0, 63 }, { 31, 31 } };
			for (int i = 0; i < 4 && r == R_PASS; i++) {
				const uint8_t *p = base + (size_t)pts[i][1] * bpr + (size_t)pts[i][0] * 4;
				if (!probe(p, 1, 0, 0, 0.5f, 0.25f, 1.0f, 1.0f)) {
					r = R_FAIL;
				}
			}
		}
		IOSurfaceUnlock(s, kIOSurfaceLockReadOnly, NULL);
	}
	CFRelease(s);
	return r;
}

static int
t16(void)
{
	if (!g_q) {
		return skip("no queue");
	}
	id<MTLTexture> t = newTarget();
	if (!t) {
		return fail("target nil");
	}
	uint64_t t0 = clock_gettime_nsec_np(CLOCK_MONOTONIC_RAW);
	for (int i = 0; i < 100; i++) {
		float v = (float)(i % 10) / 10.0f;
		id<MTLCommandBuffer> cb = [g_q commandBuffer];
		id<MTLRenderCommandEncoder> e = cb ? beginPass(cb, t, MTLClearColorMake(v, 1.0f - v, 0.5, 1.0), nil) : nil;
		if (!e) {
			return fail("pass %d: encoder nil", i);
		}
		[e endEncoding];
		char what[24];
		snprintf(what, sizeof(what), "pass %d", i);
		if (!finish(cb, what)) {
			return R_FAIL;
		}
	}
	uint64_t t1 = clock_gettime_nsec_np(CLOCK_MONOTONIC_RAW);
	static uint8_t px[W * H * 4];
	readTex(t, px, W, H);
	if (!probe(px, W, 5, 5, 0.9f, 0.1f, 0.5f, 1.0f)) {
		return R_FAIL;
	}
	note("100 passes in %llu ms", (unsigned long long)((t1 - t0) / 1000000));
	return R_PASS;
}

static int
t17(void)
{
	if (!g_q) {
		return skip("no queue");
	}
	id<MTLTexture> t = newTarget();
	id<MTLCommandBuffer> cb = t ? [g_q commandBuffer] : nil;
	id<MTLRenderCommandEncoder> e = cb ? beginPass(cb, t, MTLClearColorMake(0, 0, 0, 1), nil) : nil;
	if (!e) {
		return fail("render encoder nil");
	}
	[e endEncoding];
	dispatch_semaphore_t sem = dispatch_semaphore_create(0);
	[cb addCompletedHandler:^(id<MTLCommandBuffer> c) {
		(void)c;
		dispatch_semaphore_signal(sem);
	}];
	if (!finish(cb, "handler cb")) {
		return R_FAIL;
	}
	if (dispatch_semaphore_wait(sem, dispatch_time(DISPATCH_TIME_NOW, 5 * NSEC_PER_SEC)) != 0) {
		return fail("completion handler did not fire in 5 s");
	}
	char st[40] = "unsupported", en[40] = "unsupported";
	if ([cb respondsToSelector:@selector(GPUStartTime)]) {
		snprintf(st, sizeof(st), "%.6f", [cb GPUStartTime]);
	}
	if ([cb respondsToSelector:@selector(GPUEndTime)]) {
		snprintf(en, sizeof(en), "%.6f", [cb GPUEndTime]);
	}
	note("handler fired, GPUStartTime=%s GPUEndTime=%s", st, en);
	return R_PASS;
}

/*
 * 18/19: ONE quad with CoreAnimation's own shaders and CoreAnimation's own vertex layout
 * (QuartzCore vertex_layout_info[0]): buffer 1, per-vertex, stride 48, Float4 position @0,
 * Float2 texcoord @16, Float2 texcoord @24, Half4 colour @32. Vertices and UInt16 indices
 * share one buffer, vertices bound at a non-zero offset, as MetalBufferPool does. The four
 * vertices carry four different opaque colours; a quad whose second triangle reads its
 * colour varying from the wrong registers splits along the diagonal.
 *
 * Function constants: an EMPTY MTLFunctionConstantValues is tried first; this driver's
 * -newFunctionWithName:constantValues: returns nil (redwoodmetal.m, Metal's nil compiler),
 * and the library takes every constant as zero either way, so the fallback is the plain
 * -newFunctionWithName:, and the line says which one was used (fc=empty / fc=none).
 * Fragment buffers 0-5 are bound zero-filled because the shader declares them.
 */
#define QC_LIB "/System/Library/Frameworks/QuartzCore.framework/default.metallib"

static id<MTLFunction>
qcFunction(id<MTLLibrary> lib, NSString *name, BOOL *viaConstants)
{
	NSError *e = nil;
	MTLFunctionConstantValues *cv = [[MTLFunctionConstantValues alloc] init];
	id<MTLFunction> f = [lib newFunctionWithName:name constantValues:cv error:&e];
	*viaConstants = f != nil;
	return f ? f : [lib newFunctionWithName:name];
}

static void
hexpx(const uint8_t *px, int x, int y, char *out, size_t n)
{
	const uint8_t *p = px + ((size_t)y * W + (size_t)x) * 4;
	snprintf(out, n, "%02x%02x%02x%02x", p[2], p[1], p[0], p[3]);   /* RGBA */
}

static int
caQuad(NSString *vsName, NSString *fsName)
{
	if (!g_q) {
		return skip("no queue");
	}
	NSError *err = nil;
	id<MTLLibrary> lib = [g_dev newLibraryWithURL:[NSURL fileURLWithPath:@QC_LIB] error:&err];
	if (!lib) {
		snprintf(g_why, sizeof(g_why), "newLibraryWithURL %s: %s", QC_LIB, errstr(err));
		return R_SKIP;
	}
	BOOL vc = NO, fc = NO;
	id<MTLFunction> vs = qcFunction(lib, vsName, &vc);
	id<MTLFunction> fs = qcFunction(lib, fsName, &fc);
	if (!vs || !fs) {
		return fail("function nil (vs %s, fs %s)", vs ? "ok" : "nil", fs ? "ok" : "nil");
	}
	MTLVertexDescriptor *vd = [MTLVertexDescriptor vertexDescriptor];
	static const MTLVertexFormat fmts[4] = { MTLVertexFormatFloat4, MTLVertexFormatFloat2,
		MTLVertexFormatFloat2, MTLVertexFormatHalf4 };
	static const NSUInteger offs[4] = { 0, 16, 24, 32 };
	for (NSUInteger i = 0; i < 4; i++) {
		vd.attributes[i].format = fmts[i];
		vd.attributes[i].offset = offs[i];
		vd.attributes[i].bufferIndex = 1;
	}
	vd.layouts[1].stride = 48;
	vd.layouts[1].stepFunction = MTLVertexStepFunctionPerVertex;
	vd.layouts[1].stepRate = 1;
	MTLRenderPipelineDescriptor *d = [[MTLRenderPipelineDescriptor alloc] init];
	d.vertexFunction = vs;
	d.fragmentFunction = fs;
	d.vertexDescriptor = vd;
	d.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
	id<MTLRenderPipelineState> p = [g_dev newRenderPipelineStateWithDescriptor:d error:&err];
	if (!p) {
		return fail("pipeline nil: %s", errstr(err));
	}

	/* one pool buffer: vertices at offset 96, the six indices right after them (4-aligned) */
	enum { VOFF = 96, IOFF = VOFF + 4 * 48, POOL = 512 };
	static const float pos[4][2] = { { -1, -1 }, { 1, -1 }, { -1, 1 }, { 1, 1 } };
	/* half 1.0 = 0x3c00: red, green, blue, white, all opaque */
	static const uint16_t col[4][4] = { { 0x3c00, 0, 0, 0x3c00 }, { 0, 0x3c00, 0, 0x3c00 },
		{ 0, 0, 0x3c00, 0x3c00 }, { 0x3c00, 0x3c00, 0x3c00, 0x3c00 } };
	static const uint16_t idx[6] = { 0, 1, 2, 2, 1, 3 };
	id<MTLBuffer> pool = [g_dev newBufferWithLength:POOL options:MTLResourceStorageModeShared];
	static const float ident[16] = { 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1 };
	id<MTLBuffer> mvp = [g_dev newBufferWithBytes:ident length:64 options:MTLResourceStorageModeShared];
	id<MTLBuffer> tm = [g_dev newBufferWithBytes:ident length:64 options:MTLResourceStorageModeShared];
	id<MTLBuffer> cm = [g_dev newBufferWithBytes:ident length:64 options:MTLResourceStorageModeShared];
	id<MTLBuffer> zero = [g_dev newBufferWithLength:256 options:MTLResourceStorageModeShared];
	if (!pool || !mvp || !tm || !cm || !zero) {
		return fail("buffer nil");
	}
	uint8_t *m = [pool contents];
	memset(m, 0, POOL);
	memset([zero contents], 0, 256);
	for (int v = 0; v < 4; v++) {
		float *f = (float *)(void *)(m + VOFF + v * 48);
		f[0] = pos[v][0];
		f[1] = pos[v][1];
		f[2] = 0;
		f[3] = 1;
		f[4] = f[6] = (pos[v][0] + 1) * 0.5f;   /* texcoords: unused by the colour, but defined */
		f[5] = f[7] = (1 - pos[v][1]) * 0.5f;
		memcpy(m + VOFF + v * 48 + 32, col[v], 8);
	}
	memcpy(m + IOFF, idx, sizeof(idx));

	id<MTLTexture> t = newTarget();
	id<MTLCommandBuffer> cb = t ? [g_q commandBuffer] : nil;
	id<MTLRenderCommandEncoder> e = cb ? beginPass(cb, t, MTLClearColorMake(0, 0, 0, 1), nil) : nil;
	if (!e) {
		return fail("render encoder nil");
	}
	[e setRenderPipelineState:p];
	[e setVertexBuffer:pool offset:VOFF atIndex:1];
	[e setVertexBuffer:mvp offset:0 atIndex:2];
	[e setVertexBuffer:tm offset:0 atIndex:3];
	[e setVertexBuffer:cm offset:0 atIndex:4];
	for (NSUInteger i = 0; i <= 5; i++) {
		[e setFragmentBuffer:zero offset:0 atIndex:i];
	}
	[e drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:6 indexType:MTLIndexTypeUInt16
		indexBuffer:pool indexBufferOffset:IOFF];
	[e endEncoding];
	if (!finish(cb, "ca quad")) {
		return R_FAIL;
	}
	static uint8_t px[W * H * 4];
	readTex(t, px, W, H);

	/* NDC (-1,-1) is the bottom-left pixel: v0 (1,62) red, v1 (62,62) green, v2 (1,1) blue,
	 * v3 (62,1) white. The diagonal joins v1 and v2, the line y == x; (32,31) is in the
	 * triangle 2-1-3 and (31,32) in 0-1-2. RGBA expectations, tolerance 40. */
	static const int corner[4][2] = { { 1, 62 }, { 62, 62 }, { 1, 1 }, { 62, 1 } };
	static const uint8_t want[4][4] = { { 255, 0, 0, 255 }, { 0, 255, 0, 255 }, { 0, 0, 255, 255 },
		{ 255, 255, 255, 255 } };
	char c[4][12], ma[12], mb[12];
	BOOL ok = YES;
	for (int i = 0; i < 4; i++) {
		const uint8_t *q = px + ((size_t)corner[i][1] * W + (size_t)corner[i][0]) * 4;
		const uint8_t rgba[4] = { q[2], q[1], q[0], q[3] };
		for (int k = 0; k < 4; k++) {
			int dd = (int)rgba[k] - (int)want[i][k];
			if (dd < -40 || dd > 40) {
				ok = NO;
			}
		}
		hexpx(px, corner[i][0], corner[i][1], c[i], sizeof(c[i]));
	}
	const uint8_t *a = px + ((size_t)31 * W + 32) * 4, *b = px + ((size_t)32 * W + 31) * 4;
	for (int k = 0; k < 4; k++) {
		int dd = (int)a[k] - (int)b[k];
		if (dd <= -60 || dd >= 60) {
			ok = NO;
		}
	}
	hexpx(px, 32, 31, ma, sizeof(ma));
	hexpx(px, 31, 32, mb, sizeof(mb));
	if (!ok) {
		return fail("fc=%s c0 %s c1 %s c2 %s c3 %s mid %s/%s", vc && fc ? "empty" : "none", c[0], c[1],
			c[2], c[3], ma, mb);
	}
	note("fc=%s c0 %s c1 %s c2 %s c3 %s mid %s/%s", vc && fc ? "empty" : "none", c[0], c[1], c[2], c[3],
		ma, mb);
	return R_PASS;
}

static int
t18(void)
{
	return caQuad(@"fixed_vert_lph_spc", @"fixed_frag_lph_cph");
}

/* QuartzCore has no fixed_frag_lpf_* (only fixed_frag_lph_cph and _cpf), so the same fragment */
static int
t19(void)
{
	return caQuad(@"fixed_vert_lpf_spc", @"fixed_frag_lph_cph");
}

typedef struct { const char *name; int (*fn)(void); unsigned timeout; } Test;

int
main(int argc, char **argv)
{
	setvbuf(stdout, NULL, _IOLBF, 0);
	for (int i = 1; i < argc; i++) {
		if (strcmp(argv[i], "--delay") == 0) {
			sleep(20);
		} else {
			g_libpath = argv[i];
		}
	}
	static const Test tests[] = {
		{ "device", t01, 10 }, { "queue+empty commit", t02, 10 }, { "buffer roundtrip", t03, 10 },
		{ "texture roundtrip", t04, 10 }, { "render clear", t05, 10 }, { "library from source", t06, 10 },
		{ "library from metallib", t07, 10 }, { "solid triangle", t08, 10 }, { "textured quad", t09, 10 },
		{ "alpha blend", t10, 10 }, { "depth test", t11, 10 }, { "blit texture copy", t12, 10 },
		{ "blit mipmaps+tex2buf", t13, 10 }, { "compute", t14, 10 }, { "iosurface texture", t15, 10 },
		{ "100 passes", t16, 30 }, { "completion handler+GPU times", t17, 10 },
		{ "CA quad lph", t18, 30 }, { "CA quad lpf", t19, 30 },
	};
	int counts[3] = { 0, 0, 0 };
	int tmo_in_row = 0;
	int ntests = (int)(sizeof(tests) / sizeof(tests[0]));
	say("start, %d tests, pid %d, metallib %s", ntests, (int)getpid(), g_libpath);
	signal(SIGALRM, on_signal);
	signal(SIGSEGV, on_signal);
	signal(SIGBUS, on_signal);
	signal(SIGABRT, on_signal);
	signal(SIGILL, on_signal);
	signal(SIGTRAP, on_signal);
	for (int i = 0; i < ntests; i++) {
		volatile int r = R_FAIL;
		g_why[0] = g_note[0] = '\0';
		g_sig = 0;
		if (sigsetjmp(g_jmp, 1) == 0) {
			alarm(tests[i].timeout);
			@autoreleasepool {
				@try {
					r = tests[i].fn();
				} @catch (NSException *ex) {
					r = fail("exception %.40s: %.80s", [[ex name] UTF8String], [[ex reason] UTF8String]);
				}
			}
			alarm(0);
			tmo_in_row = 0;
		} else {
			alarm(0);
			if (g_sig == SIGALRM) {
				r = fail("timeout after %u s", tests[i].timeout);
				tmo_in_row++;
			} else {
				r = fail("crash: signal %d", (int)g_sig);
			}
		}
		counts[r]++;
		if (r == R_PASS) {
			say("%02d %s: PASS%s%s", i + 1, tests[i].name, g_note[0] ? " " : "", g_note);
		} else if (r == R_SKIP) {
			say("%02d %s: SKIP %s", i + 1, tests[i].name, g_why);
		} else {
			say("%02d %s: FAIL %s", i + 1, tests[i].name, g_why);
		}
		if (tmo_in_row >= 2) {
			say("two timeouts in a row, giving up on the rest");
			counts[R_SKIP] += ntests - i - 1;
			break;
		}
	}
	say("done %d passed %d failed %d skipped", counts[R_PASS], counts[R_FAIL], counts[R_SKIP]);
	return 0;
}
