package com.hypixelai;

import net.minecraft.client.MinecraftClient;
import org.lwjgl.nanovg.NVGColor;
import org.lwjgl.nanovg.NVGPaint;
import org.lwjgl.opengl.GL11;
import org.lwjgl.opengl.GL13;
import org.lwjgl.opengl.GL14;
import org.lwjgl.opengl.GL15;
import org.lwjgl.opengl.GL20;
import org.lwjgl.opengl.GL30;
import org.lwjgl.system.MemoryUtil;

import java.io.InputStream;
import java.nio.ByteBuffer;

import static org.lwjgl.nanovg.NanoVG.*;
import static org.lwjgl.nanovg.NanoVGGL3.*;

/**
 * NanoVG-based renderer for anti-aliased vector GUI rendering.
 * Provides smooth rounded rects, gradients, drop shadows, arcs, circles, and text.
 */
public class NVGRenderer {

    private static long vg = 0;
    private static int fontId = -1;
    private static ByteBuffer fontData;
    private static boolean initialized = false;

    // Pre-allocated temp objects — reused every frame, no allocation
    private static final NVGColor c1 = NVGColor.create();
    private static final NVGColor c2 = NVGColor.create();
    private static final NVGPaint p1 = NVGPaint.create();

    // GL state save slots
    private static final int[] savedInts = new int[9];
    private static final boolean[] savedFlags = new boolean[6];

    // ===================== Lifecycle =====================

    public static void init() {
        if (initialized) return;
        vg = nvgCreate(NVG_ANTIALIAS | NVG_STENCIL_STROKES);
        if (vg == 0) {
            HypixelAIMod.LOGGER.error("[NVG] Failed to create NanoVG context");
            return;
        }
        loadFont();
        initialized = true;
        HypixelAIMod.LOGGER.info("[NVG] Renderer initialized" + (fontId >= 0 ? " with custom font" : " (no font — using MC text)"));
    }

    private static void loadFont() {
        String[] paths = {
            "/assets/hypixelai/fonts/inter.ttf",
            "/assets/hypixelai/fonts/regular.ttf",
            "/assets/hypixelai/fonts/font.ttf"
        };
        for (String path : paths) {
            try {
                InputStream is = NVGRenderer.class.getResourceAsStream(path);
                if (is != null) {
                    byte[] data = is.readAllBytes();
                    is.close();
                    fontData = MemoryUtil.memAlloc(data.length);
                    fontData.put(data).flip();
                    fontId = nvgCreateFontMem(vg, "default", fontData, false);
                    if (fontId >= 0) return;
                }
            } catch (Exception ignored) {}
        }
    }

    public static void destroy() {
        if (vg != 0) { nvgDelete(vg); vg = 0; }
        if (fontData != null) { MemoryUtil.memFree(fontData); fontData = null; }
        initialized = false;
    }

    public static boolean isReady() { return initialized && vg != 0; }
    public static boolean hasFont() { return fontId >= 0; }

    // ===================== Frame =====================

    /**
     * Begin a frame using Minecraft's window dimensions.
     * Saves GL state that NanoVG will modify.
     */
    public static void beginFrame() {
        if (!isReady()) init();
        if (!isReady()) return;

        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.getWindow() == null) return;
        float sw = mc.getWindow().getScaledWidth();
        float sh = mc.getWindow().getScaledHeight();
        float dpr = (float) mc.getWindow().getFramebufferWidth() / sw;
        beginFrame(sw, sh, dpr);
    }

    public static void beginFrame(float width, float height, float pixelRatio) {
        if (!isReady()) return;

        // Save GL state
        savedInts[0] = GL11.glGetInteger(GL20.GL_CURRENT_PROGRAM);
        savedInts[1] = GL11.glGetInteger(GL30.GL_VERTEX_ARRAY_BINDING);
        savedInts[2] = GL11.glGetInteger(GL14.GL_BLEND_SRC_RGB);
        savedInts[3] = GL11.glGetInteger(GL14.GL_BLEND_DST_RGB);
        savedInts[4] = GL11.glGetInteger(GL14.GL_BLEND_SRC_ALPHA);
        savedInts[5] = GL11.glGetInteger(GL14.GL_BLEND_DST_ALPHA);
        savedInts[6] = GL11.glGetInteger(GL13.GL_ACTIVE_TEXTURE);
        savedInts[7] = GL11.glGetInteger(GL30.GL_FRAMEBUFFER_BINDING);
        savedInts[8] = GL11.glGetInteger(GL15.GL_ARRAY_BUFFER_BINDING);
        savedFlags[0] = GL11.glIsEnabled(GL11.GL_BLEND);
        savedFlags[1] = GL11.glIsEnabled(GL11.GL_DEPTH_TEST);
        savedFlags[2] = GL11.glIsEnabled(GL11.GL_CULL_FACE);
        savedFlags[3] = GL11.glIsEnabled(GL11.GL_SCISSOR_TEST);
        savedFlags[4] = GL11.glIsEnabled(GL11.GL_STENCIL_TEST);
        savedFlags[5] = GL11.glIsEnabled(GL11.GL_COLOR_LOGIC_OP);

        nvgBeginFrame(vg, width, height, pixelRatio);
    }

    public static void endFrame() {
        if (!isReady()) return;
        nvgEndFrame(vg);

        // Restore GL state
        GL20.glUseProgram(savedInts[0]);
        GL30.glBindVertexArray(savedInts[1]);
        GL14.glBlendFuncSeparate(savedInts[2], savedInts[3], savedInts[4], savedInts[5]);
        GL13.glActiveTexture(savedInts[6]);
        GL30.glBindFramebuffer(GL30.GL_FRAMEBUFFER, savedInts[7]);
        GL15.glBindBuffer(GL15.GL_ARRAY_BUFFER, savedInts[8]);
        setGL(GL11.GL_BLEND, savedFlags[0]);
        setGL(GL11.GL_DEPTH_TEST, savedFlags[1]);
        setGL(GL11.GL_CULL_FACE, savedFlags[2]);
        setGL(GL11.GL_SCISSOR_TEST, savedFlags[3]);
        setGL(GL11.GL_STENCIL_TEST, savedFlags[4]);
        setGL(GL11.GL_COLOR_LOGIC_OP, savedFlags[5]);
    }

    private static void setGL(int cap, boolean on) {
        if (on) GL11.glEnable(cap); else GL11.glDisable(cap);
    }

    // ===================== Color helpers =====================

    private static NVGColor color(NVGColor c, int argb, float alpha) {
        c.r(((argb >> 16) & 0xFF) / 255f);
        c.g(((argb >> 8) & 0xFF) / 255f);
        c.b((argb & 0xFF) / 255f);
        c.a((((argb >> 24) & 0xFF) / 255f) * alpha);
        return c;
    }

    private static NVGColor colorRGBA(NVGColor c, float r, float g, float b, float a) {
        c.r(r); c.g(g); c.b(b); c.a(a);
        return c;
    }

    // ===================== Shape primitives =====================

    /** Fill a rectangle. */
    public static void rect(float x, float y, float w, float h, int argb, float alpha) {
        nvgBeginPath(vg);
        nvgRect(vg, x, y, w, h);
        nvgFillColor(vg, color(c1, argb, alpha));
        nvgFill(vg);
    }

    /** Fill using (x1,y1)-(x2,y2) coordinates (like MC's fill). */
    public static void fill(float x1, float y1, float x2, float y2, int argb, float alpha) {
        rect(x1, y1, x2 - x1, y2 - y1, argb, alpha);
    }

    /** Rounded rectangle. */
    public static void roundedRect(float x, float y, float w, float h, float r, int argb, float alpha) {
        nvgBeginPath(vg);
        nvgRoundedRect(vg, x, y, w, h, r);
        nvgFillColor(vg, color(c1, argb, alpha));
        nvgFill(vg);
    }

    /** Top-rounded rectangle (flat bottom). */
    public static void roundedRectTop(float x, float y, float w, float h, float r, int argb, float alpha) {
        nvgBeginPath(vg);
        nvgRoundedRectVarying(vg, x, y, w, h, r, r, 0, 0);
        nvgFillColor(vg, color(c1, argb, alpha));
        nvgFill(vg);
    }

    /** Bottom-rounded rectangle (flat top). */
    public static void roundedRectBottom(float x, float y, float w, float h, float r, int argb, float alpha) {
        nvgBeginPath(vg);
        nvgRoundedRectVarying(vg, x, y, w, h, 0, 0, r, r);
        nvgFillColor(vg, color(c1, argb, alpha));
        nvgFill(vg);
    }

    /** Filled circle. */
    public static void circle(float cx, float cy, float radius, int argb, float alpha) {
        nvgBeginPath(vg);
        nvgCircle(vg, cx, cy, radius);
        nvgFillColor(vg, color(c1, argb, alpha));
        nvgFill(vg);
    }

    /** Filled arc segment (donut slice between outerR and outerR-thickness). */
    public static void arc(float cx, float cy, float outerR, float thickness,
                           float startAngle, float endAngle, int argb, float alpha) {
        nvgBeginPath(vg);
        nvgArc(vg, cx, cy, outerR, startAngle, endAngle, NVG_CW);
        nvgArc(vg, cx, cy, outerR - thickness, endAngle, startAngle, NVG_CCW);
        nvgClosePath(vg);
        nvgFillColor(vg, color(c1, argb, alpha));
        nvgFill(vg);
    }

    /** Anti-aliased line with round caps. */
    public static void line(float x1, float y1, float x2, float y2, float width, int argb, float alpha) {
        nvgBeginPath(vg);
        nvgMoveTo(vg, x1, y1);
        nvgLineTo(vg, x2, y2);
        nvgStrokeColor(vg, color(c1, argb, alpha));
        nvgStrokeWidth(vg, width);
        nvgLineCap(vg, NVG_ROUND);
        nvgStroke(vg);
    }

    /** Stroked rounded rectangle (outline only). */
    public static void strokeRect(float x, float y, float w, float h, float r,
                                  float strokeW, int argb, float alpha) {
        nvgBeginPath(vg);
        nvgRoundedRect(vg, x, y, w, h, r);
        nvgStrokeColor(vg, color(c1, argb, alpha));
        nvgStrokeWidth(vg, strokeW);
        nvgStroke(vg);
    }

    // ===================== Gradients =====================

    /** Horizontal linear gradient fill in a rounded rect. */
    public static void horizontalGradient(float x, float y, float w, float h, float r,
                                          int startARGB, int endARGB, float alpha) {
        nvgLinearGradient(vg, x, y, x + w, y,
                color(c1, startARGB, alpha), color(c2, endARGB, alpha), p1);
        nvgBeginPath(vg);
        nvgRoundedRect(vg, x, y, w, h, r);
        nvgFillPaint(vg, p1);
        nvgFill(vg);
    }

    /** Vertical linear gradient fill in a rounded rect. */
    public static void verticalGradient(float x, float y, float w, float h, float r,
                                        int startARGB, int endARGB, float alpha) {
        nvgLinearGradient(vg, x, y, x, y + h,
                color(c1, startARGB, alpha), color(c2, endARGB, alpha), p1);
        nvgBeginPath(vg);
        nvgRoundedRect(vg, x, y, w, h, r);
        nvgFillPaint(vg, p1);
        nvgFill(vg);
    }

    // ===================== Shadows =====================

    /** Outer drop shadow with blur. */
    public static void dropShadow(float x, float y, float w, float h, float r,
                                  float blur, int argb, float alpha) {
        nvgBoxGradient(vg, x, y + 2, w, h, r, blur,
                color(c1, argb, alpha), colorRGBA(c2, 0, 0, 0, 0), p1);
        nvgBeginPath(vg);
        nvgRect(vg, x - blur, y - blur, w + blur * 2, h + blur * 2);
        nvgRoundedRect(vg, x, y, w, h, r);
        nvgPathWinding(vg, NVG_HOLE);
        nvgFillPaint(vg, p1);
        nvgFill(vg);
    }

    /** Inner shadow / glow. */
    public static void innerShadow(float x, float y, float w, float h, float r,
                                   float blur, int argb, float alpha) {
        nvgBoxGradient(vg, x, y, w, h, r, blur,
                colorRGBA(c1, 0, 0, 0, 0), color(c2, argb, alpha), p1);
        nvgBeginPath(vg);
        nvgRoundedRect(vg, x, y, w, h, r);
        nvgFillPaint(vg, p1);
        nvgFill(vg);
    }

    // ===================== Text =====================

    /** Draw left-aligned text. Returns end X position. */
    public static float text(String text, float x, float y, float size, int argb, float alpha) {
        if (fontId < 0 || text == null || text.isEmpty()) return x;
        nvgFontFaceId(vg, fontId);
        nvgFontSize(vg, size);
        nvgFillColor(vg, color(c1, argb, alpha));
        nvgTextAlign(vg, NVG_ALIGN_LEFT | NVG_ALIGN_TOP);
        return nvgText(vg, x, y, text);
    }

    /** Draw center-aligned text. */
    public static float textCentered(String text, float cx, float y, float size, int argb, float alpha) {
        if (fontId < 0 || text == null || text.isEmpty()) return cx;
        nvgFontFaceId(vg, fontId);
        nvgFontSize(vg, size);
        nvgFillColor(vg, color(c1, argb, alpha));
        nvgTextAlign(vg, NVG_ALIGN_CENTER | NVG_ALIGN_TOP);
        return nvgText(vg, cx, y, text);
    }

    /** Draw right-aligned text. */
    public static float textRight(String text, float rx, float y, float size, int argb, float alpha) {
        if (fontId < 0 || text == null || text.isEmpty()) return rx;
        nvgFontFaceId(vg, fontId);
        nvgFontSize(vg, size);
        nvgFillColor(vg, color(c1, argb, alpha));
        nvgTextAlign(vg, NVG_ALIGN_RIGHT | NVG_ALIGN_TOP);
        return nvgText(vg, rx, y, text);
    }

    /** Measure text width at given size. */
    public static float textWidth(String text, float size) {
        if (fontId < 0 || text == null || text.isEmpty()) return 0;
        nvgFontFaceId(vg, fontId);
        nvgFontSize(vg, size);
        float[] bounds = new float[4];
        nvgTextBounds(vg, 0, 0, text, bounds);
        return bounds[2] - bounds[0];
    }

    // ===================== Scissor =====================

    public static void scissor(float x, float y, float w, float h) { nvgScissor(vg, x, y, w, h); }
    public static void resetScissor() { nvgResetScissor(vg); }

    // ===================== Transform =====================

    public static void save() { nvgSave(vg); }
    public static void restore() { nvgRestore(vg); }
    public static void globalAlpha(float a) { nvgGlobalAlpha(vg, a); }
}
