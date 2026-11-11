// Shaders for metaltest. Kept in step with kShaderSource in metaltest.m (test 06 compiles that copy on device).
#include <metal_stdlib>
using namespace metal;

struct VOut {
	float4 pos [[position]];
	float2 uv;
};

// buffer(0): one float4 per vertex (x, y, u, v); buffer(1): z
vertex VOut vs_main(uint vid [[vertex_id]], constant float4 *v [[buffer(0)]], constant float &z [[buffer(1)]])
{
	VOut o;
	o.pos = float4(v[vid].xy, z, 1.0);
	o.uv = v[vid].zw;
	return o;
}

fragment float4 fs_color(VOut in [[stage_in]], constant float4 &c [[buffer(0)]])
{
	return c;
}

fragment float4 fs_tex(VOut in [[stage_in]], texture2d<float> t [[texture(0)]])
{
	constexpr sampler s(filter::nearest, address::clamp_to_edge);
	return t.sample(s, in.uv);
}

kernel void k_double(device uint *out [[buffer(0)]], uint i [[thread_position_in_grid]])
{
	out[i] = i * 2;
}
