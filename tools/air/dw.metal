/*
 * Shaders for air_metal_test --draw-deferred (0011's deferred wait, and 0016's submit
 * without the wait). Not shipped: a host-side proof only.
 *
 *   xcrun -sdk iphoneos metal -c -mios-version-min=16.0 -DENTRY_fs_pos  dw.metal -o dw-pos.air
 *   xcrun -sdk iphoneos metal -c -mios-version-min=16.0 -DENTRY_fs_copy dw.metal -o dw-copy.air
 *   xcrun -sdk iphoneos metallib dw-pos.air dw-copy.air -o dw.metallib
 *   air_metal_test --draw-deferred dw.metallib
 *
 * One function per compilation on purpose: a .metallib holds one LLVM module per function,
 * and the library takes a module's own entry point, so a module holding both can answer for
 * only the first of them ("this module's entry point is fs_pos").
 *
 * There is no vertex function: a draw with no vertex stream is given a fullscreen quad by
 * the library, and [[position]] is the pixel centre, which is what the test expects.
 *
 * fs_pos writes the pixel's own position with a constant's z, so a wrong colour or a wrong
 * pixel is visible; fs_copy reads that target and adds half to z.
 */
#include <metal_stdlib>
using namespace metal;

#if defined(ENTRY_fs_pos)

fragment float4 fs_pos(float4 position [[position]], constant float4 &c [[buffer(0)]])
{
	return float4(position.xy, c.z, 1.0);
}

#elif defined(ENTRY_fs_copy)

fragment float4 fs_copy(float4 position [[position]], texture2d<float> t [[texture(0)]])
{
	return t.read(uint2(position.xy)) + float4(0.0, 0.0, 0.5, 0.0);
}

#else
#error "define ENTRY_fs_pos or ENTRY_fs_copy"
#endif
