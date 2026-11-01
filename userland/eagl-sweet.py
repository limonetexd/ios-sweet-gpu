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

open(dst, 'w').write(c)
print('eagl-sweet: applied')
