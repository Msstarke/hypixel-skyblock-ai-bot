package com.hypixelai;

import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.render.RenderTickCounter;
import net.minecraft.text.OrderedText;
import net.minecraft.text.Text;

import java.util.ArrayList;
import java.util.List;

/**
 * Clean floating HUD overlay for AI responses.
 * Non-interactive, auto-sizes to content, fades in/out.
 */
public class SkyAIOverlay implements HudRenderCallback {

    // Colors (ARGB)
    private static final int BG_OUTER    = 0xCC101018; // outer shadow layer
    private static final int BG_MAIN     = 0xEE14141E; // main background
    private static final int BG_HEADER   = 0xFF1A1A28; // header strip
    private static final int BORDER      = 0xFF2A2A3A; // subtle border
    private static final int ACCENT      = 0xFF00BBEE; // cyan accent
    private static final int TEXT_BODY   = 0xFFBBBBBB; // body text
    private static final int TEXT_WHITE  = 0xFFEEEEEE; // bright text
    private static final int TEXT_MUTED  = 0xFF666677; // muted
    private static final int BULLET_COL  = 0xFFFFAA00; // gold
    private static final int NUM_COL     = 0xFF00BBEE; // cyan

    // Layout
    private static final int MARGIN_RIGHT = 10;
    private static final int MARGIN_TOP = 10;
    private static final int PADDING = 10;
    private static final int HEADER_HEIGHT = 18;
    private static final int LINE_HEIGHT = 11;
    private static final int MAX_WIDTH = 260;
    private static final int MIN_WIDTH = 160;

    // State
    private static String currentQuestion = null;
    private static List<OverlayLine> currentLines = null;
    private static long showTime = 0;
    private static long hideTime = 0;
    private static final long FADE_IN_MS = 200;
    private static final long DISPLAY_MS = 15000; // show for 15 seconds
    private static final long FADE_OUT_MS = 500;

    // Thinking state
    private static boolean thinking = false;
    private static long thinkingStart = 0;

    public static void show(String question, String[] responseLines) {
        MinecraftClient client = MinecraftClient.getInstance();
        if (client == null || client.textRenderer == null) return;

        TextRenderer tr = client.textRenderer;
        int wrapWidth = MAX_WIDTH - PADDING * 2;

        List<OverlayLine> lines = new ArrayList<>();
        for (String line : responseLines) {
            if (line.isEmpty()) {
                lines.add(new OverlayLine("", LineType.SPACER, 0));
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

            // Word wrap
            List<OrderedText> wrapped = tr.wrapLines(Text.literal(content), wrapWidth - indent);
            for (int i = 0; i < wrapped.size(); i++) {
                LineType t = (i == 0) ? type : (type == LineType.BULLET ? LineType.BULLET_CONT : LineType.NORMAL);
                // Convert OrderedText back to string for storage
                StringBuilder sb = new StringBuilder();
                wrapped.get(i).accept((index, style, codePoint) -> {
                    sb.appendCodePoint(codePoint);
                    return true;
                });
                lines.add(new OverlayLine(sb.toString(), t, indent));
            }
        }

        currentQuestion = question;
        currentLines = lines;
        showTime = System.currentTimeMillis();
        hideTime = 0;
        thinking = false;
    }

    public static void showThinking(String question) {
        currentQuestion = question;
        currentLines = null;
        thinking = true;
        thinkingStart = System.currentTimeMillis();
        showTime = System.currentTimeMillis();
        hideTime = 0;
    }

    public static void hide() {
        if (hideTime == 0 && (currentLines != null || thinking)) {
            hideTime = System.currentTimeMillis();
        }
    }

    public static void clear() {
        currentQuestion = null;
        currentLines = null;
        thinking = false;
        showTime = 0;
        hideTime = 0;
    }

    public static void register() {
        HudRenderCallback.EVENT.register(new SkyAIOverlay());
    }

    @Override
    public void onHudRender(DrawContext context, RenderTickCounter tickCounter) {
        if (currentQuestion == null && !thinking) return;

        long now = System.currentTimeMillis();

        // Auto-hide after display time
        if (hideTime == 0 && currentLines != null) {
            long elapsed = now - showTime;
            if (elapsed > DISPLAY_MS) {
                hideTime = now;
            }
        }

        // Calculate alpha for fade in/out
        float alpha;
        if (hideTime > 0) {
            float fadeOut = 1f - (float)(now - hideTime) / FADE_OUT_MS;
            if (fadeOut <= 0) {
                clear();
                return;
            }
            alpha = fadeOut;
        } else {
            alpha = Math.min(1f, (float)(now - showTime) / FADE_IN_MS);
        }

        MinecraftClient client = MinecraftClient.getInstance();
        if (client == null) return;
        TextRenderer tr = client.textRenderer;
        int screenW = client.getWindow().getScaledWidth();

        // Calculate content dimensions
        int contentW;
        int contentH;

        if (thinking) {
            contentW = MIN_WIDTH;
            contentH = HEADER_HEIGHT + PADDING + LINE_HEIGHT + PADDING;
        } else if (currentLines != null) {
            // Find widest line
            int maxLineW = tr.getWidth(currentQuestion);
            for (OverlayLine line : currentLines) {
                if (line.type != LineType.SPACER) {
                    int w = tr.getWidth(line.text) + line.indent + 8;
                    if (w > maxLineW) maxLineW = w;
                }
            }
            contentW = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, maxLineW + PADDING * 2 + 8));
            int linesHeight = 0;
            for (OverlayLine line : currentLines) {
                linesHeight += (line.type == LineType.SPACER) ? 6 : LINE_HEIGHT;
            }
            contentH = HEADER_HEIGHT + PADDING + linesHeight + PADDING;
        } else {
            return;
        }

        // Position: top right with margin
        int x = screenW - contentW - MARGIN_RIGHT;
        int y = MARGIN_TOP;

        // Shadow layers (soft shadow effect)
        drawRect(context, x + 2, y + 2, contentW, contentH, applyAlpha(0x40000000, alpha));
        drawRect(context, x + 1, y + 1, contentW, contentH, applyAlpha(0x60000000, alpha));

        // Main background
        drawRect(context, x, y, contentW, contentH, applyAlpha(BG_MAIN, alpha));

        // Border
        drawRectOutline(context, x, y, contentW, contentH, applyAlpha(BORDER, alpha));

        // Header background
        drawRect(context, x + 1, y + 1, contentW - 2, HEADER_HEIGHT - 1, applyAlpha(BG_HEADER, alpha));

        // Accent line under header
        drawRect(context, x + 1, y + HEADER_HEIGHT - 1, contentW - 2, 1, applyAlpha(ACCENT, alpha));

        // Header text
        String title = "\u25C6 SkyAI";
        context.drawTextWithShadow(tr, title, x + PADDING, y + 5, applyAlpha(ACCENT, alpha));

        // Version on right of header
        String ver = "v" + HypixelAIUpdater.MOD_VERSION;
        int verW = tr.getWidth(ver);
        context.drawText(tr, ver, x + contentW - verW - PADDING, y + 5,
                applyAlpha(TEXT_MUTED, alpha), false);

        // Content area
        int cy = y + HEADER_HEIGHT + PADDING;

        if (thinking) {
            // Thinking animation (dots)
            long dots = ((now - thinkingStart) / 400) % 4;
            String thinkText = "Thinking" + ".".repeat((int)dots);
            context.drawText(tr, thinkText, x + PADDING, cy, applyAlpha(TEXT_MUTED, alpha), false);
        } else if (currentLines != null) {
            for (OverlayLine line : currentLines) {
                if (line.type == LineType.SPACER) {
                    cy += 6;
                    continue;
                }

                int lx = x + PADDING + line.indent;

                switch (line.type) {
                    case BULLET:
                        context.drawText(tr, "\u2022", x + PADDING, cy,
                                applyAlpha(BULLET_COL, alpha), false);
                        context.drawText(tr, line.text, lx + 8, cy,
                                applyAlpha(TEXT_BODY, alpha), false);
                        break;

                    case BULLET_CONT:
                        context.drawText(tr, line.text, lx + 8, cy,
                                applyAlpha(TEXT_BODY, alpha), false);
                        break;

                    case NUMBERED:
                        int dotIdx = line.text.indexOf('.');
                        if (dotIdx > 0 && dotIdx < 4) {
                            String num = line.text.substring(0, dotIdx + 1);
                            String rest = line.text.substring(dotIdx + 1).trim();
                            context.drawText(tr, num, lx, cy,
                                    applyAlpha(NUM_COL, alpha), false);
                            int numW = tr.getWidth(num + " ");
                            context.drawText(tr, rest, lx + numW, cy,
                                    applyAlpha(TEXT_BODY, alpha), false);
                        } else {
                            context.drawText(tr, line.text, lx, cy,
                                    applyAlpha(TEXT_BODY, alpha), false);
                        }
                        break;

                    default:
                        context.drawText(tr, line.text, lx, cy,
                                applyAlpha(TEXT_BODY, alpha), false);
                        break;
                }
                cy += LINE_HEIGHT;
            }
        }
    }

    // --- Drawing helpers ---

    private static void drawRect(DrawContext ctx, int x, int y, int w, int h, int color) {
        ctx.fill(x, y, x + w, y + h, color);
    }

    private static void drawRectOutline(DrawContext ctx, int x, int y, int w, int h, int color) {
        ctx.fill(x, y, x + w, y + 1, color);         // top
        ctx.fill(x, y + h - 1, x + w, y + h, color); // bottom
        ctx.fill(x, y, x + 1, y + h, color);          // left
        ctx.fill(x + w - 1, y, x + w, y + h, color);  // right
    }

    private static int applyAlpha(int argb, float alpha) {
        int a = (argb >> 24) & 0xFF;
        a = (int)(a * alpha);
        return (a << 24) | (argb & 0x00FFFFFF);
    }

    // --- Data types ---

    private enum LineType {
        NORMAL, BULLET, BULLET_CONT, NUMBERED, SPACER
    }

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
