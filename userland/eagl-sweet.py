#!/usr/bin/env python3
"""Sweet changes to ios-topaz's userland/gpu/eagl.c, applied at build time.

    userland/eagl-sweet.py IN_EAGL_C OUT_EAGL_C

1. A surface CoreAnimation draws into (attachImage, blit_targets) gets the frame it
   last held loaded into the library's texture by the GPU (a blit from the
   texture that is the surface's memory) instead of by the processor
   (surface_changed + glTexImage2D of the whole surface). Run 0097t: ~415 ms a
   frame went to that upload (glTexImage2D, 11 MB) on the A618 port.
"""
import sys

src, dst = sys.argv[1], sys.argv[2]
c = open(src).read()


def sub(old, new):
    global c
    if c.count(old) != 1:
        sys.exit('eagl-sweet: anchor found %d times: %r' % (c.count(old), old[:60]))
    c = c.replace(old, new)


MIRROR_LOAD = '''/*
 * sweet: what the surface holds (the last frame drawn into it) into the texture CoreAnimation
 * draws into, by the GPU: a blit from the texture that is the surface's memory (image->mirror),
 * the other way from target_to_surface(), upside down if it is drawn so. The texture keeps its
 * storage when it has the size already. The texture is bound and stays bound.
 */
static void
mirror_to_texture(struct eagl *e, struct image *image)
{
	GLint read = 0, draw = 0, had_width = 0, had_height = 0;

	glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, 0x1000, &had_width);
	glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, 0x1001, &had_height);
	if (had_width != image->width || had_height != image->height) {
		glTexImage2D(GL_TEXTURE_2D, 0, GL_BGRA, image->width, image->height, 0, GL_BGRA, GL_UNSIGNED_BYTE, NULL);
	}
	glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &read);
	glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &draw);
	if (e->reader == 0) {
		glGenFramebuffers(1, &e->reader);
	}
	if (e->writer == 0) {
		glGenFramebuffers(1, &e->writer);
	}
	glBindFramebuffer(GL_READ_FRAMEBUFFER, e->reader);
	glFramebufferTexture2D(GL_READ_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, image->mirror, 0);
	glBindFramebuffer(GL_DRAW_FRAMEBUFFER, e->writer);
	glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, image->texture, 0);
	glBlitFramebuffer(0, 0, image->width, image->height, 0, image->invert ? image->height : 0, image->width,
	    image->invert ? 0 : image->height, GL_COLOR_BUFFER_BIT, GL_NEAREST);
	glBindFramebuffer(GL_READ_FRAMEBUFFER, (GLuint)read);
	glBindFramebuffer(GL_DRAW_FRAMEBUFFER, (GLuint)draw);
	image->seed = IOSurfaceGetSeed(image->surface);
}

/* (the "image" is the target, GL_TEXTURE_2D, and means the texture bound to it) */
'''
sub('/* (the "image" is the target, GL_TEXTURE_2D, and means the texture bound to it) */\n', MIRROR_LOAD)

sub('''	if (surface_mirrored(e, image) || !surface_shared(e, image)) {
		surface_changed(e, image);              /* (what it adds up to now) */
		surface_to_texture(e, image);
	}
	e->attaching += now_us() - began;
	if (attached++ < 24) {''', '''	if (surface_mirrored(e, image)) {
		mirror_to_texture(e, image);            /* sweet: by the GPU */
	} else if (!surface_shared(e, image)) {
		surface_changed(e, image);              /* (what it adds up to now) */
		surface_to_texture(e, image);
	}
	e->attaching += now_us() - began;
	if (attached++ < 24) {''')


# ---------------------------------------------------------------------------------------------
# 2. Reuse of what is kept per IOSurface between frames (proposed, see reports/research-2026-11-06-eagl-reuse.md).
#    Every change has a switch read once at start-up from the environment (boot-arg glenv=NAME=VALUE sets it
#    for backboardd); the frame line "redwood-gl: frame N: ..." gets a "| sweet:" tail with the counters.
#      SWEET_GL_ATTACH_REUSE=1  attachImage on the texture+surface it already has: no new mirror, no load blit
#      SWEET_GL_TEX_REUSE=1     texImageIOSurface on the same texture+surface: no re-wrap, no 11 MB re-upload
#      SWEET_GL_FASTSUM=1       the "has the memory changed" sum with 4 independent lanes (same cost model, ~3x faster)
#      SWEET_GL_SUM_LADDER=0    ... looked at every 4th / 8th frame once it has been quiet for 90 / 240 looks
#      SWEET_GL_FRESH_CLEAR=0   a surface nobody has written (seed 0): a clear instead of the load blit
#      SWEET_GL_MIRROR_POOL=0   N (<= 8): keep N mirror textures of retired surfaces, to find them again by surface ID
#      SWEET_GL_INFLIGHT=0      N (<= 4): at most N frames not yet finished by the GPU (waits on the oldest fence)
#      SWEET_GL_STATS=1         the "| sweet:" tail
# ---------------------------------------------------------------------------------------------
def tabs(text):
    out = []
    for line in text.split('\n'):
        n = len(line) - len(line.lstrip(' '))
        out.append('\t' * (n // 4) + ' ' * (n % 4) + line[n:])
    return '\n'.join(out)


# the struct image and struct eagl: new fields
sub('/* A texture that stands for an IOSurface. */\n', tabs('''#define SW_POOL 8
static void sw_summary(void);
static const char *sw_suffix(void);

/* A texture that stands for an IOSurface. */
'''))
sub('\tuint32_t plane, seed;\n\tGLsizei width, height;\n};', tabs('''    uint32_t plane, seed;
    GLsizei width, height;
    bool valid;                     /* sweet: the texture holds what it was made to hold (nobody has glTexImage2D'd it since) */
    uint64_t cost_us;               /* ... and what making it cost (the time a reuse saves) */
};'''))
sub('\tunsigned plain_said;\n};', tabs('''    unsigned plain_said;
    struct {                        /* sweet: mirror textures of surfaces that were let go of (SWEET_GL_MIRROR_POOL) */
        GLuint mirror;
        uint32_t id;
        IOSurfaceRef surface;
    } pool[SW_POOL];
    unsigned pool_next;
    GLsync fences[4];               /* ... and the fences of the frames not known to be finished (SWEET_GL_INFLIGHT) */
    unsigned fence_head, fence_count;
};'''))

# helpers: after image_of(), before image_new()
SW_HELPERS = tabs('''/* ---- sweet: what is kept between frames --------------------------------------------------------- */

static int sw_stats = 1, sw_attach_reuse = 1, sw_tex_reuse = 1, sw_fast_sum = 1, sw_sum_ladder, sw_fresh_clear;
static unsigned sw_pool_max, sw_inflight_max;
static struct sw_counters {             /* (all uint64_t: sw_roll() adds them up as an array) */
    uint64_t attach_hit, attach_blit, attach_miss, attach_hit_us, attach_miss_us;
    uint64_t tex_hit, tex_upload, tex_miss, tex_hit_us, tex_miss_us;
    uint64_t pool_hit, pool_miss, fresh, fresh_cleared, hashes, hash_us, deletes, delete_us;
    uint64_t wrap_us, alloc_us, blit_us, wait_us, saved_us;
} sw_f, sw_all;                         /* this frame's, and everything so far */

static long
sw_env(const char *name, long fallback)
{
    const char *value = getenv(name);

    return value != NULL && *value != 0 ? strtol(value, NULL, 0) : fallback;
}

static void
sw_init(void)
{
    long pool, inflight;

    sw_stats = sw_env("SWEET_GL_STATS", 1) != 0;
    sw_attach_reuse = sw_env("SWEET_GL_ATTACH_REUSE", 1) != 0;
    sw_tex_reuse = sw_env("SWEET_GL_TEX_REUSE", 1) != 0;
    sw_fast_sum = sw_env("SWEET_GL_FASTSUM", 1) != 0;
    sw_sum_ladder = sw_env("SWEET_GL_SUM_LADDER", 0) != 0;
    sw_fresh_clear = sw_env("SWEET_GL_FRESH_CLEAR", 0) != 0;
    pool = sw_env("SWEET_GL_MIRROR_POOL", 0);
    inflight = sw_env("SWEET_GL_INFLIGHT", 0);
    sw_pool_max = pool < 0 ? 0 : pool > SW_POOL ? SW_POOL : (unsigned)pool;
    sw_inflight_max = inflight < 0 ? 0 : inflight > 4 ? 4 : (unsigned)inflight;
    say("redwood-gl: sweet reuse: attach %d, texIOSurface %d, fastsum %d, sum ladder %d, fresh clear %d, mirror pool %u, "
        "in flight %u, stats %d\\n", sw_attach_reuse, sw_tex_reuse, sw_fast_sum, sw_sum_ladder, sw_fresh_clear, sw_pool_max,
        sw_inflight_max, sw_stats);
}

/* The sum of a memory, four words at a time (the sum of one lane waits for its own last result, about 4 cycles a word). */
static uint64_t
sw_sum(const uint8_t *base, size_t size)
{
    const uint64_t k = 0x9e3779b97f4a7c15ull;
    uint64_t lane[4] = { size, size ^ 1, size ^ 2, size ^ 3 }, word[4];
    size_t at = 0;

    for (; at + 32 <= size; at += 32) {
        memcpy(word, base + at, 32);
        for (int i = 0; i < 4; i++) {
            lane[i] = (lane[i] ^ word[i]) * k;
            lane[i] ^= lane[i] >> 29;
        }
    }
    for (; at + 8 <= size; at += 8) {
        memcpy(word, base + at, 8);
        lane[0] = (lane[0] ^ word[0]) * k;
        lane[0] ^= lane[0] >> 29;
    }
    return ((((lane[0] * k) ^ lane[1]) * k ^ lane[2]) * k) ^ lane[3];
}

/* How many frames go by between two sums of a memory that has been the same for `quiet` sums. */
static unsigned
sw_sum_period(unsigned quiet)
{
    return sw_sum_ladder ? (quiet >= 240 ? 8 : quiet >= 90 ? 4 : 2) : 2;
}

/* The texture bound to the unit is about to be given new contents by somebody else: it is no longer what it was made. */
static void
sw_invalidate(struct eagl *e, GLenum target)
{
    struct image *image;

    if (target == GL_TEXTURE_2D && e->unit < 8 && e->bound[e->unit] != 0 && (image = image_of(e, e->bound[e->unit])) != NULL) {
        image->valid = false;
    }
}

static void
sw_pool_drop(struct eagl *e, unsigned slot)
{
    if (e->pool[slot].mirror != 0) {
        glDeleteTextures(1, &e->pool[slot].mirror);
        CFRelease(e->pool[slot].surface);
    }
    memset(&e->pool[slot], 0, sizeof(e->pool[slot]));
}

/* A mirror texture is not needed any more: kept for its surface (SWEET_GL_MIRROR_POOL), or deleted. */
static void
sw_mirror_release(struct eagl *e, struct image *image)
{
    uint32_t id;
    unsigned slot = SW_POOL;
    bool known = false;

    if (image->mirror == 0) {
        return;
    }
    id = IOSurfaceGetID(image->surface);
    if (sw_pool_max != 0 && id != 0) {
        for (unsigned i = 0; i < sw_pool_max; i++) {
            known |= e->pool[i].mirror != 0 && e->pool[i].id == id;
            if (slot == SW_POOL && e->pool[i].mirror == 0) {
                slot = i;
            }
        }
        if (!known) {
            if (slot == SW_POOL) {
                slot = e->pool_next++ % sw_pool_max;
                sw_pool_drop(e, slot);
            }
            e->pool[slot].mirror = image->mirror;
            e->pool[slot].id = id;
            e->pool[slot].surface = (IOSurfaceRef)CFRetain(image->surface);
            image->mirror = 0;
            return;
        }
    }
    glDeleteTextures(1, &image->mirror);
    image->mirror = 0;
}

/* The mirror texture kept for this surface, or 0. */
static GLuint
sw_mirror_take(struct eagl *e, uint32_t id)
{
    for (unsigned i = 0; sw_pool_max != 0 && i < sw_pool_max; i++) {
        if (e->pool[i].mirror != 0 && e->pool[i].id == id) {
            GLuint mirror = e->pool[i].mirror;

            CFRelease(e->pool[i].surface);
            memset(&e->pool[i], 0, sizeof(e->pool[i]));
            sw_f.pool_hit++;
            return mirror;
        }
    }
    if (sw_pool_max != 0) {
        sw_f.pool_miss++;
    }
    return 0;
}

/* A frame's fence (flushed, not waited for): at most sw_inflight_max of them are not waited for yet. */
static void
sw_fence_push(struct eagl *e, GLsync sync)
{
    unsigned slot;

    if (sw_inflight_max == 0) {
        glDeleteSync(sync);
        return;
    }
    slot = e->fence_head % sw_inflight_max;
    if (e->fence_count == sw_inflight_max) {
        uint64_t began = now_us();

        (void)glClientWaitSync(e->fences[slot], 0, 30000000ull);        /* (the oldest; 30 ms at the most) */
        glDeleteSync(e->fences[slot]);
        sw_f.wait_us += now_us() - began;
    } else {
        e->fence_count++;
    }
    e->fences[slot] = sync;
    e->fence_head++;
}

static void
sw_roll(void)
{
    uint64_t *all = (uint64_t *)&sw_all;
    const uint64_t *frame = (const uint64_t *)&sw_f;

    for (unsigned i = 0; i < sizeof(sw_f) / sizeof(uint64_t); i++) {
        all[i] += frame[i];
    }
    memset(&sw_f, 0, sizeof(sw_f));
}

/* The tail of the frame line. */
static const char *
sw_suffix(void)
{
    static char text[520];

    if (!sw_stats) {
        return "";
    }
    snprintf(text, sizeof(text), " | sweet: attach hit %llu (%llu blit) miss %llu %llu us; texIOS hit %llu (%llu up) miss %llu "
        "%llu us; pool %llu/%llu; fresh %llu clr %llu; wrap %llu alloc %llu blit %llu us; del %llu x %llu us; hash %llu x %llu us; "
        "wait %llu us; saved~%llu us [all: attach %llu/%llu, tex %llu/%llu, saved~%llu ms]", sw_f.attach_hit, sw_f.attach_blit,
        sw_f.attach_miss, sw_f.attach_miss_us, sw_f.tex_hit, sw_f.tex_upload, sw_f.tex_miss, sw_f.tex_miss_us, sw_f.pool_hit,
        sw_f.pool_miss, sw_f.fresh, sw_f.fresh_cleared, sw_f.wrap_us, sw_f.alloc_us, sw_f.blit_us, sw_f.deletes, sw_f.delete_us,
        sw_f.hashes, sw_f.hash_us, sw_f.wait_us, sw_f.saved_us, sw_all.attach_hit + sw_f.attach_hit,
        sw_all.attach_hit + sw_all.attach_miss + sw_f.attach_hit + sw_f.attach_miss, sw_all.tex_hit + sw_f.tex_hit,
        sw_all.tex_hit + sw_all.tex_miss + sw_f.tex_hit + sw_f.tex_miss, (sw_all.saved_us + sw_f.saved_us) / 1000);
    return text;
}

static void
sw_summary(void)
{
    say("redwood-gl: sweet totals: attach hit %llu (%llu with a load blit) miss %llu; texIOS hit %llu (%llu uploads) miss %llu; "
        "pool hit %llu miss %llu; fresh surfaces %llu (cleared %llu); hashes %llu, %llu us; deletes %llu, %llu us; "
        "in-flight waits %llu us; saved~%llu ms\\n", sw_all.attach_hit, sw_all.attach_blit, sw_all.attach_miss, sw_all.tex_hit,
        sw_all.tex_upload, sw_all.tex_miss, sw_all.pool_hit, sw_all.pool_miss, sw_all.fresh, sw_all.fresh_cleared,
        sw_all.hashes, sw_all.hash_us, sw_all.deletes, sw_all.delete_us, sw_all.wait_us, sw_all.saved_us / 1000);
}

''')
sub('static struct image *\nimage_new(struct eagl *e, GLuint texture, IOSurfaceRef surface)\n{',
    SW_HELPERS + 'static struct image *\nimage_new(struct eagl *e, GLuint texture, IOSurfaceRef surface)\n{')

# image_new / image_forget: the mirror goes through sw_mirror_release()
sub('\t} else {\n\t\tif (image->mirror != 0) {\n\t\t\tglDeleteTextures(1, &image->mirror);\n\t\t}\n\t\tCFRelease(image->surface);\n\t}',
    '\t} else {\n\t\tsw_mirror_release(e, image);\n\t\tCFRelease(image->surface);\n\t}')
sub('\tif (image != NULL) {\n\t\tif (image->mirror != 0) {\n\t\t\tglDeleteTextures(1, &image->mirror);\n\t\t}\n\t\tCFRelease(image->surface);\n\t\t*image =',
    '\tif (image != NULL) {\n\t\tsw_mirror_release(e, image);\n\t\tCFRelease(image->surface);\n\t\t*image =')

# surface_changed(): lanes, the period of the ladder, and the time the sums take
sub('\tif (image->quiet >= 30 && image->looked != 0 && e->frames + 1 - image->looked < 2) {',
    '\tif (image->quiet >= 30 && image->looked != 0 && e->frames + 1 - image->looked < sw_sum_period(image->quiet)) {')
sub('\timage->looked = e->frames + 1;\n\tfor (size_t at = 0; at + 8 <= size; at += 8) {\n\t\tmemcpy(&word, base + at, 8);\n\t\tsum = (sum ^ word) * 0x9e3779b97f4a7c15ull;\n\t\tsum ^= sum >> 29;\n\t}\n',
    tabs('''    image->looked = e->frames + 1;
    uint64_t sw_began = now_us();
    if (sw_fast_sum) {
        sum = sw_sum(base, size);
    } else {
        for (size_t at = 0; at + 8 <= size; at += 8) {
            memcpy(&word, base + at, 8);
            sum = (sum ^ word) * 0x9e3779b97f4a7c15ull;
            sum ^= sum >> 29;
        }
    }
    sw_f.hashes++;
    sw_f.hash_us += now_us() - sw_began;
'''))

# surface_mirrored(): a mirror kept for the surface; the time of the wrap
sub('\tglGetIntegerv(GL_TEXTURE_BINDING_2D, &bound);\n\tglGenTextures(1, &image->mirror);\n\tglBindTexture(GL_TEXTURE_2D, image->mirror);\n\tif (!redwood_gl_surface_texture(e->gl, IOSurfaceGetID(surface))) {\n',
    tabs('''    if ((image->mirror = sw_mirror_take(e, IOSurfaceGetID(surface))) != 0) {
        e->shared++;
        return true;
    }
    uint64_t sw_began = now_us();
    glGetIntegerv(GL_TEXTURE_BINDING_2D, &bound);
    glGenTextures(1, &image->mirror);
    glBindTexture(GL_TEXTURE_2D, image->mirror);
    int sw_wrapped = redwood_gl_surface_texture(e->gl, IOSurfaceGetID(surface));
    sw_f.wrap_us += now_us() - sw_began;
    if (!sw_wrapped) {
'''))

# mirror_to_texture(): the times, and the fresh surface
sub('\tif (had_width != image->width || had_height != image->height) {\n\t\tglTexImage2D(GL_TEXTURE_2D, 0, GL_BGRA, image->width, image->height, 0, GL_BGRA, GL_UNSIGNED_BYTE, NULL);\n\t}\n',
    tabs('''    if (had_width != image->width || had_height != image->height) {
        uint64_t sw_began = now_us();
        glTexImage2D(GL_TEXTURE_2D, 0, GL_BGRA, image->width, image->height, 0, GL_BGRA, GL_UNSIGNED_BYTE, NULL);
        sw_f.alloc_us += now_us() - sw_began;
    }
'''))
sub('\tglBlitFramebuffer(0, 0, image->width, image->height, 0, image->invert ? image->height : 0, image->width,\n'
    '\t    image->invert ? 0 : image->height, GL_COLOR_BUFFER_BIT, GL_NEAREST);\n'
    '\tglBindFramebuffer(GL_READ_FRAMEBUFFER, (GLuint)read);\n'
    '\tglBindFramebuffer(GL_DRAW_FRAMEBUFFER, (GLuint)draw);\n'
    '\timage->seed = IOSurfaceGetSeed(image->surface);\n',
    tabs('''    {
        static unsigned sw_told;
        uint64_t sw_began = now_us();
        uint32_t sw_seed = IOSurfaceGetSeed(image->surface);

        sw_f.fresh += sw_seed == 0;
        if (sw_told++ < 12) {
            say("redwood-gl: sweet: load of surface %u: seed %u%s\\n", IOSurfaceGetID(image->surface), sw_seed,
                sw_seed == 0 ? " (never written)" : "");
        }
        if (sw_seed == 0 && sw_fresh_clear) {
            GLfloat sw_was[4];

            /* (nothing in it: a clear is the same as the blit, and reads no 11 MB; CoreAnimation's clear colour is put back) */
            glGetFloatv(GL_COLOR_CLEAR_VALUE, sw_was);
            glClearColor(0, 0, 0, 0);
            glClear(GL_COLOR_BUFFER_BIT);
            glClearColor(sw_was[0], sw_was[1], sw_was[2], sw_was[3]);
            sw_f.fresh_cleared++;
        } else {
            glBlitFramebuffer(0, 0, image->width, image->height, 0, image->invert ? image->height : 0, image->width,
                image->invert ? 0 : image->height, GL_COLOR_BUFFER_BIT, GL_NEAREST);
        }
        sw_f.blit_us += now_us() - sw_began;
    }
    glBindFramebuffer(GL_READ_FRAMEBUFFER, (GLuint)read);
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, (GLuint)draw);
    image->seed = IOSurfaceGetSeed(image->surface);
'''))

# target_to_surface(): the seed after our own write (lock/unlock) is the seed the next attachImage finds if nobody else wrote
sub('\t\tif (IOSurfaceLock(surface, 0, NULL) == 0) {\n\t\t\tIOSurfaceUnlock(surface, 0, NULL);\n\t\t}\n\t\treturn;\n\t}\n\tif (image->shared) {',
    '\t\tif (IOSurfaceLock(surface, 0, NULL) == 0) {\n\t\t\tIOSurfaceUnlock(surface, 0, NULL);\n\t\t}\n\t\timage->seed = IOSurfaceGetSeed(surface);       /* sweet: (see my_attachImage()) */\n\t\treturn;\n\t}\n\tif (image->shared) {')

# frame_end(): the fence goes to the ring; the counters are rolled; the tail of the line
sub('\t\tif (sync != NULL) {\n\t\t\t(void)glClientWaitSync(sync, GL_SYNC_FLUSH_COMMANDS_BIT, 0);\n\t\t\tglDeleteSync(sync);\n\t\t}',
    '\t\tif (sync != NULL) {\n\t\t\t(void)glClientWaitSync(sync, GL_SYNC_FLUSH_COMMANDS_BIT, 0);\n\t\t\tsw_fence_push(e, sync);\n\t\t}')
sub('"out), %llu before it for the IOSurfaces\\n", e->frames,', '"out), %llu before it for the IOSurfaces%s\\n", e->frames,')
sub('after - waited, e->attaching);', 'after - waited, e->attaching, sw_suffix());')
sub('\te->upload_bytes = e->attaching = e->flushing = 0;\n', '\te->upload_bytes = e->attaching = e->flushing = 0;\n\tsw_roll();\n')
sub('\tfor (unsigned i = 0; i < sizeof(formats) / sizeof(formats[0]) && formats[i].count; i++) {\n\t\tsay("redwood-gl:   textures:',
    '\tsw_summary();\n\tfor (unsigned i = 0; i < sizeof(formats) / sizeof(formats[0]) && formats[i].count; i++) {\n\t\tsay("redwood-gl:   textures:')

# glDeleteTextures: the time; the calls that give a texture new contents
sub('\t\tif (textures[i] == e->colour) {\n\t\t\te->colour = 0;          /* (a texture that is deleted leaves the framebuffer bound) */\n\t\t}\n\t}\n\tglDeleteTextures(n, textures);\n',
    '\t\tif (textures[i] == e->colour) {\n\t\t\te->colour = 0;          /* (a texture that is deleted leaves the framebuffer bound) */\n\t\t}\n\t}\n\tglDeleteTextures(n, textures);\n\tsw_f.deletes++;\n\tsw_f.delete_us += now_us() - e->gl_t0;\n')
sub('\tclear_now(e);\n\tif (target == GL_TEXTURE_2D && e->unit < 8) {\n\t\tgroup_forget(e, e->bound[e->unit]);\n\t}\n',
    '\tclear_now(e);\n\tsw_invalidate(e, target);\n\tif (target == GL_TEXTURE_2D && e->unit < 8) {\n\t\tgroup_forget(e, e->bound[e->unit]);\n\t}\n')
sub('\tglTexSubImage2D(target, level, x, y, width, height, format, type, pixels);\n\tEAGL_LEAVE(e, 0x9a0);',
    '\tsw_invalidate(e, target);\n\tglTexSubImage2D(target, level, x, y, width, height, format, type, pixels);\n\tEAGL_LEAVE(e, 0x9a0);')
sub('\tglCopyTexSubImage2D(target, level, x0, y0, x, y, width, height);\n\tEAGL_LEAVE(e, 0x1c8);',
    '\tsw_invalidate(e, target);\n\tglCopyTexSubImage2D(target, level, x0, y0, x, y, width, height);\n\tEAGL_LEAVE(e, 0x1c8);')
sub('\tglCompressedTexImage2D(target, level, internal, width, height, border, size, data);\n',
    '\tsw_invalidate(e, target);\n\tglCompressedTexImage2D(target, level, internal, width, height, border, size, data);\n')

# -texImageIOSurface: the same texture made of the same surface again
sub('\tglGetIntegerv(GL_TEXTURE_BINDING_2D, &texture);\n\tif (target != GL_TEXTURE_2D || texture == 0 || (image = image_new(e, (GLuint)texture, surface)) == NULL) {\n\t\tsay("redwood-gl: -texImageIOSurface',
    tabs('''    glGetIntegerv(GL_TEXTURE_BINDING_2D, &texture);
    if (sw_tex_reuse && target == GL_TEXTURE_2D && texture != 0 && (image = image_of(e, (GLuint)texture)) != NULL &&
        image->valid && !image->target && IOSurfaceGetID(image->surface) == IOSurfaceGetID(surface) &&
        image->to == (GLenum)target && image->internal == (GLenum)internal && image->format == (GLenum)format &&
        image->type == (GLenum)type && image->plane == plane && image->invert == (invert != 0) && image->width == width &&
        image->height == height) {
        /* the texture holds this surface already: a shared one is the surface; a copy is made again only if it has changed */
        uint64_t sw_began = now_us();

        if (!image->shared) {
            bool sw_moved = IOSurfaceGetSeed(surface) != image->seed;

            if (surface_changed(e, image) || sw_moved) {
                surface_to_texture(e, image);
                sw_f.tex_upload++;
            }
        }
        sw_f.tex_hit++;
        sw_f.tex_hit_us += now_us() - sw_began;
        sw_f.saved_us += image->cost_us;
        e->attaching += now_us() - sw_began;
        eagl_leave(e, 0x970);
        return YES;
    }
    if (target != GL_TEXTURE_2D || texture == 0 || (image = image_new(e, (GLuint)texture, surface)) == NULL) {
        say("redwood-gl: -texImageIOSurface'''))
sub('\te->attaching += now_us() - began;\n\teagl_leave(e, 0x970);\n\treturn YES;',
    '\te->attaching += now_us() - began;\n\timage->valid = true;\n\timage->cost_us = now_us() - began;\n\tsw_f.tex_miss++;\n\tsw_f.tex_miss_us += image->cost_us;\n\teagl_leave(e, 0x970);\n\treturn YES;')

# -attachImage: the same texture drawn into on the same surface again: its mirror is there, and the texture is what the surface holds
# unless somebody has written to the surface since the last frame left it (its seed has moved)
sub('\tpixels = IOSurfaceGetPixelFormat(surface);\n\tif (target != GL_TEXTURE_2D || texture == 0 ||',
    tabs('''    pixels = IOSurfaceGetPixelFormat(surface);
    if (sw_attach_reuse && target == GL_TEXTURE_2D && texture != 0 && (image = image_of(e, (GLuint)texture)) != NULL &&
        image->valid && image->target && image->mirror != 0 && IOSurfaceGetID(image->surface) == IOSurfaceGetID(surface) &&
        image->invert == (inverted != 0) && image->alpha_first == (pixels == 0) &&
        image->width == (GLsizei)IOSurfaceGetWidth(surface) && image->height == (GLsizei)IOSurfaceGetHeight(surface)) {
        uint64_t sw_began = now_us();

        if (IOSurfaceGetSeed(surface) != image->seed) {
            mirror_to_texture(e, image);            /* (someone else wrote: load it again, into the storage it has) */
            sw_f.attach_blit++;
        }
        sw_f.attach_hit++;
        sw_f.attach_hit_us += now_us() - sw_began;
        sw_f.saved_us += image->cost_us;
        e->attaching += now_us() - sw_began;
        eagl_leave(e, 0x970);
        return YES;
    }
    if (target != GL_TEXTURE_2D || texture == 0 ||'''))
sub('\te->attaching += now_us() - began;\n\tif (attached++ < 24) {',
    '\te->attaching += now_us() - began;\n\timage->valid = true;\n\timage->cost_us = now_us() - began;\n\tsw_f.attach_miss++;\n\tsw_f.attach_miss_us += image->cost_us;\n\tif (attached++ < 24) {')

# start-up
sub('\tif (class == Nil) {\n', '\tsw_init();\n\tif (class == Nil) {\n')


open(dst, 'w').write(c)
print('eagl-sweet: applied')
