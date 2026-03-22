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
 * macOS terminal-style dark panel with traffic light dots.
 */
public class SkyAIOverlay implements HudRenderCallback {

    // Colors (ARGB)
    private static final int BG_MAIN      = 0xF01E1E2E; // dark purple-ish bg
    private static final int BG_HEADER    = 0xFF282840; // slightly lighter header
    private static final int ACCENT_LINE  = 0xFF00BBEE; // blue accent
    private static final int TEXT_TITLE   = 0xFF00DDFF; // cyan title
    private static final int TEXT_BODY    = 0xFFCCCCCC; // light gray body
    private static final int TEXT_MUTED   = 0xFF777788; // muted text
    private static final int BULLET_COL   = 0xFFFFAA00; // orange bullets
    private static final int NUM_COL      = 0xFF00BBEE; // blue numbers
    private static final int DOT_RED      = 0xFFFF5F57;
    private static final int DOT_YELLOW   = 0xFFFFBD2E;
    private static final int DOT_GREEN    = 0xFF28C840;
    private static final int SHADOW_COL   = 0x40000000; // subtle shadow
    private static final int BORDER_COL   = 0xFF333355; // subtle border

    // Layout
    private static final int MARGIN_RIGHT = 8;
    private static final int MARGIN_TOP = 8;
    private static final int PADDING = 10;
    private static final int HEADER_HEIGHT = 18;
    private static final int LINE_HEIGHT = 11;
    private static final int MAX_WIDTH = 260;
    private static final int MIN_WIDTH = 160;

    // State (set from any thread)
    private static volatile String currentQuestion = null;
    private static volatile String[] rawLines = null;
    private static volatile boolean thinking = false;
    private static volatile long showTime = 0;
    private static volatile long hideTime = 0;
    private static volatile long thinkingStart = 0;

    // Processed lines (built on render thread)
    private static List<OverlayLine> processedLines = null;
    private static String[] processedFrom = null;

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

        // Auto-hide after display time
        if (hideTime == 0 && processedLines != null) {
            if (now - showTime > DISPLAY_MS) hideTime = now;
        }

        // Alpha for fade in/out
        float alpha;
        if (hideTime > 0) {
            float fadeOut = 1f - (float)(now - hideTime) / FADE_OUT_MS;
            if (fadeOut <= 0) { clear(); return; }
            alpha = fadeOut;
        } else {
            alpha = Math.min(1f, (float)(now - showTime) / FADE_IN_MS);
        }

        // Calculate content dimensions
        int contentW, contentH;
        if (thinking) {
            contentW = MIN_WIDTH;
            contentH = HEADER_HEIGHT + 1 + PADDING + LINE_HEIGHT + PADDING;
        } else if (processedLines != null) {
            int maxLineW = 0;
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
            contentH = HEADER_HEIGHT + 1 + PADDING + linesH + PADDING;
        } else {
            return;
        }

        // Position: top-right corner
        int x = screenW - contentW - MARGIN_RIGHT;
        int y = MARGIN_TOP;

        // --- Draw the panel ---

        // Shadow (offset down-right by 2px)
        fillAlpha(context, x + 2, y + 2, x + contentW + 2, y + contentH + 2, SHADOW_COL, alpha);

        // Border (1px around the whole panel)
        fillAlpha(context, x - 1, y - 1, x + contentW + 1, y + contentH + 1, BORDER_COL, alpha);

        // Main background
        fillAlpha(context, x, y, x + contentW, y + contentH, BG_MAIN, alpha);

        // Header background
        fillAlpha(context, x, y, x + contentW, y + HEADER_HEIGHT, BG_HEADER, alpha);

        // Accent line under header
        fillAlpha(context, x, y + HEADER_HEIGHT, x + contentW, y + HEADER_HEIGHT + 1, ACCENT_LINE, alpha);

        // Traffic light dots (3x3 filled squares for clean look at this scale)
        int dotY = y + HEADER_HEIGHT / 2 - 1;
        int dotX = x + 8;
        int dotSize = 3;
        int dotGap = 6;
        fillAlpha(context, dotX, dotY, dotX + dotSize, dotY + dotSize, DOT_RED, alpha);
        dotX += dotGap;
        fillAlpha(context, dotX, dotY, dotX + dotSize, dotY + dotSize, DOT_YELLOW, alpha);
        dotX += dotGap;
        fillAlpha(context, dotX, dotY, dotX + dotSize, dotY + dotSize, DOT_GREEN, alpha);

        // Title text "SkyAI"
        int titleX = x + 8 + dotGap * 3 + 4;
        context.drawText(tr, "SkyAI", titleX, y + (HEADER_HEIGHT - 8) / 2, applyAlpha(TEXT_TITLE, alpha), false);

        // Version text
        String ver = "v" + HypixelAIUpdater.MOD_VERSION;
        int verW = tr.getWidth(ver);
        context.drawText(tr, ver, x + contentW - verW - PADDING, y + (HEADER_HEIGHT - 8) / 2,
                applyAlpha(TEXT_MUTED, alpha), false);

        // Content area
        int cy = y + HEADER_HEIGHT + 1 + PADDING;

        if (thinking) {
            long dots = ((now - thinkingStart) / 400) % 4;
            String thinkText = "Thinking" + ".".repeat((int)dots);
            context.drawText(tr, thinkText, x + PADDING, cy, applyAlpha(TEXT_MUTED, alpha), false);
        } else if (processedLines != null) {
            int tx = x + PADDING;
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
                            context.drawText(tr, rest, lx + tr.getWidth(num + " "), cy,
                                    applyAlpha(TEXT_BODY, alpha), false);
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

    /**
     * Fill a rectangle with alpha applied to the color.
     */
    private static void fillAlpha(DrawContext context, int x1, int y1, int x2, int y2, int argb, float alpha) {
        int a = (int)(((argb >> 24) & 0xFF) * alpha);
        if (a <= 0) return;
        context.fill(x1, y1, x2, y2, (a << 24) | (argb & 0x00FFFFFF));
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
