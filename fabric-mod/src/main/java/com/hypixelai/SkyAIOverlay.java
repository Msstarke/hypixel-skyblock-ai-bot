package com.hypixelai;

import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.render.RenderTickCounter;
import net.minecraft.client.texture.NativeImage;
import net.minecraft.client.texture.NativeImageBackedTexture;
import net.minecraft.text.OrderedText;
import net.minecraft.text.Text;
import net.minecraft.util.Identifier;

import java.util.ArrayList;
import java.util.List;

/**
 * Clean floating HUD overlay for AI responses.
 * Uses NativeImage textures for smooth, anti-aliased rendering.
 */
public class SkyAIOverlay implements HudRenderCallback {

    // Colors (ARGB for NativeImage)
    private static final int BG_MAIN     = 0xF0141420;
    private static final int BG_HEADER   = 0xFF1C1C2C;
    private static final int ACCENT      = 0xFF00BBEE;
    private static final int TEXT_BODY   = 0xFFBBBBBB;
    private static final int TEXT_MUTED  = 0xFF666677;
    private static final int BULLET_COL  = 0xFFFFAA00;
    private static final int NUM_COL     = 0xFF00BBEE;

    // Layout
    private static final int MARGIN_RIGHT = 8;
    private static final int MARGIN_TOP = 8;
    private static final int PADDING = 10;
    private static final int HEADER_HEIGHT = 20;
    private static final int LINE_HEIGHT = 11;
    private static final int MAX_WIDTH = 260;
    private static final int MIN_WIDTH = 160;
    private static final int CORNER_RADIUS = 6;
    private static final int SHADOW_SIZE = 4;
    private static final int DOT_RADIUS = 4;

    // State — raw data (set from any thread)
    private static volatile String currentQuestion = null;
    private static volatile String[] rawLines = null;
    private static volatile boolean thinking = false;
    private static volatile long showTime = 0;
    private static volatile long hideTime = 0;
    private static volatile long thinkingStart = 0;

    // Processed lines (built on render thread)
    private static List<OverlayLine> processedLines = null;
    private static String[] processedFrom = null;

    // Texture cache
    private static NativeImageBackedTexture cachedTexture = null;
    private static Identifier textureId = null;
    private static int cachedW = 0, cachedH = 0;

    private static final long FADE_IN_MS = 200;
    private static final long DISPLAY_MS = 15000;
    private static final long FADE_OUT_MS = 500;

    public static void show(String question, String[] responseLines) {
        currentQuestion = question;
        rawLines = responseLines;
        processedLines = null;
        processedFrom = null;
        showTime = System.currentTimeMillis();
        hideTime = 0;
        thinking = false;
    }

    public static void showThinking(String question) {
        currentQuestion = question;
        rawLines = null;
        processedLines = null;
        processedFrom = null;
        thinking = true;
        thinkingStart = System.currentTimeMillis();
        showTime = System.currentTimeMillis();
        hideTime = 0;
    }

    public static void hide() {
        if (hideTime == 0 && (rawLines != null || thinking)) {
            hideTime = System.currentTimeMillis();
        }
    }

    public static void clear() {
        currentQuestion = null;
        rawLines = null;
        processedLines = null;
        processedFrom = null;
        thinking = false;
        showTime = 0;
        hideTime = 0;
    }

    public static void register() {
        HudRenderCallback.EVENT.register(new SkyAIOverlay());
    }

    private static void processLines(TextRenderer tr, String[] lines) {
        int wrapWidth = MAX_WIDTH - PADDING * 2;
        List<OverlayLine> result = new ArrayList<>();

        for (String line : lines) {
            if (line.isEmpty()) {
                result.add(new OverlayLine("", LineType.SPACER, 0));
                continue;
            }

            LineType type = LineType.NORMAL;
            String content = line;
            int indent = 0;

            if (line.startsWith("- ") || line.startsWith("* ")) {
                type = LineType.BULLET;
                content = line.substring(2);
                indent = 8;
            } else if (line.matches("^\\d+\\.\\s.*")) {
                type = LineType.NUMBERED;
                indent = 4;
            }

            List<OrderedText> wrapped = tr.wrapLines(Text.literal(content), wrapWidth - indent);
            for (int i = 0; i < wrapped.size(); i++) {
                LineType t = (i == 0) ? type : (type == LineType.BULLET ? LineType.BULLET_CONT : LineType.NORMAL);
                StringBuilder sb = new StringBuilder();
                wrapped.get(i).accept((index, style, codePoint) -> {
                    sb.appendCodePoint(codePoint);
                    return true;
                });
                result.add(new OverlayLine(sb.toString(), t, indent));
            }
        }

        processedLines = result;
    }

    // --- Smooth texture generation ---

    private static void generateTexture(int w, int h) {
        MinecraftClient client = MinecraftClient.getInstance();
        if (client == null) return;

        // Clean up old texture
        if (cachedTexture != null) {
            cachedTexture.close();
        }

        // Full size including shadow
        int fullW = w + SHADOW_SIZE * 2;
        int fullH = h + SHADOW_SIZE * 2;

        NativeImage image = new NativeImage(NativeImage.Format.RGBA, fullW, fullH, true);

        // Draw shadow (multiple passes for soft shadow)
        for (int pass = SHADOW_SIZE; pass >= 1; pass--) {
            float shadowAlpha = 0.12f * (SHADOW_SIZE - pass + 1);
            int shadowColor = ((int)(shadowAlpha * 255) << 24);
            drawRoundedRect(image, SHADOW_SIZE - pass + 1, SHADOW_SIZE - pass + 2,
                    w + pass * 2 - 2, h + pass * 2 - 2, CORNER_RADIUS + pass, shadowColor);
        }

        // Main window background
        drawRoundedRect(image, SHADOW_SIZE, SHADOW_SIZE, w, h, CORNER_RADIUS, BG_MAIN);

        // Header background (top portion with rounded top corners)
        drawRoundedRectTop(image, SHADOW_SIZE, SHADOW_SIZE, w, HEADER_HEIGHT, CORNER_RADIUS, BG_HEADER);

        // Accent line under header
        for (int px = SHADOW_SIZE + 1; px < SHADOW_SIZE + w - 1; px++) {
            image.setColorArgb(px, SHADOW_SIZE + HEADER_HEIGHT, ACCENT);
        }

        // Traffic light dots
        int dotY = SHADOW_SIZE + HEADER_HEIGHT / 2;
        int dotX1 = SHADOW_SIZE + 10;
        drawCircle(image, dotX1, dotY, DOT_RADIUS, 0xFFFF5F57);             // red
        drawCircle(image, dotX1 + DOT_RADIUS * 2 + 4, dotY, DOT_RADIUS, 0xFFFFBD2E); // yellow
        drawCircle(image, dotX1 + (DOT_RADIUS * 2 + 4) * 2, dotY, DOT_RADIUS, 0xFF28C840); // green

        // Create and register texture
        cachedTexture = new NativeImageBackedTexture("skyai_overlay", fullW, fullH, false);
        cachedTexture.setImage(image);
        cachedTexture.upload();

        if (textureId == null) {
            textureId = Identifier.of("hypixelai", "overlay_bg");
        }
        client.getTextureManager().registerTexture(textureId, cachedTexture);

        cachedW = fullW;
        cachedH = fullH;
    }

    /**
     * Draw a filled rounded rectangle with anti-aliased edges.
     */
    private static void drawRoundedRect(NativeImage image, int x, int y, int w, int h, int r, int color) {
        int a = (color >> 24) & 0xFF;
        int cr = (color >> 16) & 0xFF;
        int cg = (color >> 8) & 0xFF;
        int cb = color & 0xFF;

        for (int py = y; py < y + h; py++) {
            for (int px = x; px < x + w; px++) {
                if (px < 0 || py < 0 || px >= image.getWidth() || py >= image.getHeight()) continue;

                float dist = roundedRectSDF(px - x, py - y, w, h, r);
                if (dist > 1.0f) continue;

                float pixelAlpha = (dist < -1.0f) ? 1.0f : (1.0f - Math.max(0, dist + 1.0f) / 2.0f);
                int finalAlpha = (int)(a * pixelAlpha);

                if (finalAlpha <= 0) continue;

                // Alpha blend with existing pixel
                int existing = image.getColorArgb(px, py);
                int ea = (existing >> 24) & 0xFF;
                int er = (existing >> 16) & 0xFF;
                int eg = (existing >> 8) & 0xFF;
                int eb = existing & 0xFF;

                float srcA = finalAlpha / 255.0f;
                float dstA = ea / 255.0f;
                float outA = srcA + dstA * (1 - srcA);

                int outR, outG, outB, outAi;
                if (outA > 0) {
                    outR = (int)((cr * srcA + er * dstA * (1 - srcA)) / outA);
                    outG = (int)((cg * srcA + eg * dstA * (1 - srcA)) / outA);
                    outB = (int)((cb * srcA + eb * dstA * (1 - srcA)) / outA);
                    outAi = (int)(outA * 255);
                } else {
                    outR = outG = outB = outAi = 0;
                }

                image.setColorArgb(px, py, (outAi << 24) | (outR << 16) | (outG << 8) | outB);
            }
        }
    }

    /**
     * Draw only the top portion of a rounded rect (rounded top, flat bottom).
     */
    private static void drawRoundedRectTop(NativeImage image, int x, int y, int w, int h, int r, int color) {
        int a = (color >> 24) & 0xFF;
        int cr = (color >> 16) & 0xFF;
        int cg = (color >> 8) & 0xFF;
        int cb = color & 0xFF;

        for (int py = y; py < y + h; py++) {
            for (int px = x; px < x + w; px++) {
                if (px < 0 || py < 0 || px >= image.getWidth() || py >= image.getHeight()) continue;

                // For top-rounded rect: only round the top corners
                float dist = roundedRectTopSDF(px - x, py - y, w, h, r);
                if (dist > 1.0f) continue;

                float pixelAlpha = (dist < -1.0f) ? 1.0f : (1.0f - Math.max(0, dist + 1.0f) / 2.0f);
                int finalAlpha = (int)(a * pixelAlpha);
                if (finalAlpha <= 0) continue;

                // Overwrite (header is opaque over bg)
                image.setColorArgb(px, py, (finalAlpha << 24) | (cr << 16) | (cg << 8) | cb);
            }
        }
    }

    /**
     * Draw a smooth anti-aliased filled circle.
     */
    private static void drawCircle(NativeImage image, int cx, int cy, int radius, int color) {
        int a = (color >> 24) & 0xFF;
        int cr = (color >> 16) & 0xFF;
        int cg = (color >> 8) & 0xFF;
        int cb = color & 0xFF;

        for (int py = cy - radius - 1; py <= cy + radius + 1; py++) {
            for (int px = cx - radius - 1; px <= cx + radius + 1; px++) {
                if (px < 0 || py < 0 || px >= image.getWidth() || py >= image.getHeight()) continue;

                float dx = px - cx + 0.5f;
                float dy = py - cy + 0.5f;
                float dist = (float)Math.sqrt(dx * dx + dy * dy) - radius;

                if (dist > 1.0f) continue;
                float pixelAlpha = (dist < -1.0f) ? 1.0f : (1.0f - Math.max(0, dist + 1.0f) / 2.0f);
                int finalAlpha = (int)(a * pixelAlpha);
                if (finalAlpha <= 0) continue;

                image.setColorArgb(px, py, (finalAlpha << 24) | (cr << 16) | (cg << 8) | cb);
            }
        }
    }

    /**
     * Signed distance function for a rounded rectangle.
     * Returns negative inside, positive outside, ~0 at the edge.
     */
    private static float roundedRectSDF(float px, float py, float w, float h, float r) {
        // Center-relative coords
        float cx = px - w / 2f + 0.5f;
        float cy = py - h / 2f + 0.5f;
        float hw = w / 2f - r;
        float hh = h / 2f - r;
        float dx = Math.max(Math.abs(cx) - hw, 0);
        float dy = Math.max(Math.abs(cy) - hh, 0);
        return (float)Math.sqrt(dx * dx + dy * dy) - r;
    }

    /**
     * SDF for a rectangle with only the top corners rounded.
     */
    private static float roundedRectTopSDF(float px, float py, float w, float h, float r) {
        float cx = px - w / 2f + 0.5f;
        float cy = py - h / 2f + 0.5f;

        // Only round top corners
        if (cy > -h / 2f + r) {
            // Below the rounding zone — sharp edges
            return (Math.abs(cx) > w / 2f || cy > h / 2f || cy < -h / 2f) ? 1.0f : -1.0f;
        }

        // Top portion — rounded
        float hw = w / 2f - r;
        float hh = h / 2f - r;
        float dx = Math.max(Math.abs(cx) - hw, 0);
        float dy = Math.max(-cy - hh, 0); // only top edge
        if (Math.abs(cx) > w / 2f || cy > h / 2f) return 1.0f;
        return (float)Math.sqrt(dx * dx + dy * dy) - r;
    }

    // --- Render ---

    @Override
    public void onHudRender(DrawContext context, RenderTickCounter tickCounter) {
        if (currentQuestion == null && !thinking) return;

        long now = System.currentTimeMillis();

        MinecraftClient client = MinecraftClient.getInstance();
        if (client == null) return;
        TextRenderer tr = client.textRenderer;
        int screenW = client.getWindow().getScaledWidth();

        // Lazy-process raw lines on render thread
        String[] raw = rawLines;
        if (raw != null && (processedLines == null || processedFrom != raw)) {
            processLines(tr, raw);
            processedFrom = raw;
        }

        // Auto-hide
        if (hideTime == 0 && processedLines != null) {
            if (now - showTime > DISPLAY_MS) hideTime = now;
        }

        // Alpha
        float alpha;
        if (hideTime > 0) {
            float fadeOut = 1f - (float)(now - hideTime) / FADE_OUT_MS;
            if (fadeOut <= 0) { clear(); return; }
            alpha = fadeOut;
        } else {
            alpha = Math.min(1f, (float)(now - showTime) / FADE_IN_MS);
        }

        // Calculate dimensions
        int contentW, contentH;
        if (thinking) {
            contentW = MIN_WIDTH;
            contentH = HEADER_HEIGHT + PADDING + LINE_HEIGHT + PADDING;
        } else if (processedLines != null) {
            int maxLineW = tr.getWidth(currentQuestion != null ? currentQuestion : "");
            for (OverlayLine line : processedLines) {
                if (line.type != LineType.SPACER) {
                    int w = tr.getWidth(line.text) + line.indent + 8;
                    if (w > maxLineW) maxLineW = w;
                }
            }
            contentW = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, maxLineW + PADDING * 2 + 8));
            int linesH = 0;
            for (OverlayLine line : processedLines) {
                linesH += (line.type == LineType.SPACER) ? 6 : LINE_HEIGHT;
            }
            contentH = HEADER_HEIGHT + PADDING + linesH + PADDING;
        } else {
            return;
        }

        // Regenerate texture if size changed
        int fullW = contentW + SHADOW_SIZE * 2;
        int fullH = contentH + SHADOW_SIZE * 2;
        if (textureId == null || cachedW != fullW || cachedH != fullH) {
            generateTexture(contentW, contentH);
        }

        // Position: top right
        int x = screenW - contentW - MARGIN_RIGHT - SHADOW_SIZE;
        int y = MARGIN_TOP - SHADOW_SIZE;

        // Draw the background texture
        if (textureId != null) {
            // Draw the texture quad (deprecated overload is fine for HUD)
            @SuppressWarnings("deprecation")
            int dummy = 0;
            context.drawTexturedQuad(textureId, x, x + fullW, y, y + fullH, 0f, 1f, 0f, 1f);
        }

        // Draw text on top
        int tx = x + SHADOW_SIZE + PADDING;
        int ty = y + SHADOW_SIZE;

        // Title text
        String title = "SkyAI";
        // Position after the dots
        int titleX = x + SHADOW_SIZE + 10 + (DOT_RADIUS * 2 + 4) * 3 + 6;
        context.drawTextWithShadow(tr, title, titleX, ty + 6, applyAlpha(ACCENT, alpha));

        // Version
        String ver = "v" + HypixelAIUpdater.MOD_VERSION;
        int verW = tr.getWidth(ver);
        context.drawText(tr, ver, x + SHADOW_SIZE + contentW - verW - PADDING, ty + 6,
                applyAlpha(TEXT_MUTED, alpha), false);

        // Content
        int cy = ty + HEADER_HEIGHT + PADDING + 2;

        if (thinking) {
            long dots = ((now - thinkingStart) / 400) % 4;
            String thinkText = "Thinking" + ".".repeat((int)dots);
            context.drawText(tr, thinkText, tx, cy, applyAlpha(TEXT_MUTED, alpha), false);
        } else if (processedLines != null) {
            for (OverlayLine line : processedLines) {
                if (line.type == LineType.SPACER) { cy += 6; continue; }

                int lx = tx + line.indent;

                switch (line.type) {
                    case BULLET:
                        context.drawText(tr, "\u2022", tx, cy, applyAlpha(BULLET_COL, alpha), false);
                        context.drawText(tr, line.text, lx + 8, cy, applyAlpha(TEXT_BODY, alpha), false);
                        break;
                    case BULLET_CONT:
                        context.drawText(tr, line.text, lx + 8, cy, applyAlpha(TEXT_BODY, alpha), false);
                        break;
                    case NUMBERED:
                        int dotIdx = line.text.indexOf('.');
                        if (dotIdx > 0 && dotIdx < 4) {
                            String num = line.text.substring(0, dotIdx + 1);
                            String rest = line.text.substring(dotIdx + 1).trim();
                            context.drawText(tr, num, lx, cy, applyAlpha(NUM_COL, alpha), false);
                            context.drawText(tr, rest, lx + tr.getWidth(num + " "), cy, applyAlpha(TEXT_BODY, alpha), false);
                        } else {
                            context.drawText(tr, line.text, lx, cy, applyAlpha(TEXT_BODY, alpha), false);
                        }
                        break;
                    default:
                        context.drawText(tr, line.text, lx, cy, applyAlpha(TEXT_BODY, alpha), false);
                        break;
                }
                cy += LINE_HEIGHT;
            }
        }
    }

    private static int applyAlpha(int argb, float alpha) {
        int a = (argb >> 24) & 0xFF;
        a = (int)(a * alpha);
        return (a << 24) | (argb & 0x00FFFFFF);
    }

    private enum LineType { NORMAL, BULLET, BULLET_CONT, NUMBERED, SPACER }

    private static class OverlayLine {
        final String text;
        final LineType type;
        final int indent;
        OverlayLine(String text, LineType type, int indent) {
            this.text = text;
            this.type = type;
            this.indent = indent;
        }
    }
}
