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
 * Polished floating HUD overlay for AI responses.
 * Supports § color codes, pixel art elements, and formatted text.
 */
public class SkyAIOverlay implements HudRenderCallback {

    // Layout
    private static final int MARGIN_RIGHT = 10;
    private static final int MARGIN_TOP = 10;
    private static final int PADDING_X = 10;
    private static final int PADDING_Y = 8;
    private static final int HEADER_HEIGHT = 14;
    private static final int QUESTION_HEIGHT = 12;
    private static final int LINE_HEIGHT = 11;
    private static final int MAX_WIDTH = 280;
    private static final int MIN_WIDTH = 180;
    private static final int R = 3;

    // Color map for § codes
    private static final int COLOR_BLACK      = 0xFF000000;
    private static final int COLOR_DARK_BLUE   = 0xFF0000AA;
    private static final int COLOR_DARK_GREEN  = 0xFF00AA00;
    private static final int COLOR_DARK_AQUA   = 0xFF00AAAA;
    private static final int COLOR_DARK_RED    = 0xFFAA0000;
    private static final int COLOR_DARK_PURPLE = 0xFFAA00AA;
    private static final int COLOR_GOLD        = 0xFFFFAA00;
    private static final int COLOR_GRAY        = 0xFFAAAAAA;
    private static final int COLOR_DARK_GRAY   = 0xFF555555;
    private static final int COLOR_BLUE        = 0xFF5555FF;
    private static final int COLOR_GREEN       = 0xFF55FF55;
    private static final int COLOR_AQUA        = 0xFF55FFFF;
    private static final int COLOR_RED         = 0xFFFF5555;
    private static final int COLOR_LIGHT_PURPLE= 0xFFFF55FF;
    private static final int COLOR_YELLOW      = 0xFFFFFF55;
    private static final int COLOR_WHITE       = 0xFFFFFFFF;
    private static final int COLOR_BODY        = 0xFFCCCCCC;

    // HOTM grid cell size
    private static final int CELL_SIZE = 7;
    private static final int CELL_GAP = 1;

    // State (set from any thread)
    private static volatile String currentQuestion = null;
    private static volatile String[] rawLines = null;
    private static volatile int[] hotmGrid = null; // 70 ints: 10 tiers x 7 cols
    private static volatile boolean thinking = false;
    private static volatile long showTime = 0;
    private static volatile long hideTime = 0;
    private static volatile long thinkingStart = 0;

    // Processed lines (render thread only)
    private static List<OverlayLine> processedLines = null;
    private static String[] processedFrom = null;

    private static final long FADE_IN_MS = 200;
    private static final long DISPLAY_MS = 30000;
    private static final long FADE_OUT_MS = 500;

    public static void show(String question, String[] responseLines) {
        show(question, responseLines, null);
    }

    public static void show(String question, String[] responseLines, int[] hotmData) {
        currentQuestion = question;
        rawLines = responseLines;
        hotmGrid = hotmData;
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
        hotmGrid = null;
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
        int wrapWidth = MAX_WIDTH - PADDING_X * 2;
        List<OverlayLine> result = new ArrayList<>();

        for (String line : lines) {
            if (line.isEmpty()) {
                result.add(new OverlayLine("", LineType.SPACER, 0, null));
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

            // Strip color codes for width calculation
            String stripped = content.replaceAll("§.", "");
            int availWidth = wrapWidth - indent;

            // Simple word wrapping with color code awareness
            if (tr.getWidth(stripped) <= availWidth) {
                result.add(new OverlayLine(content, type, indent, parseColorSegments(content)));
            } else {
                // Wrap by words
                String[] words = content.split(" ");
                StringBuilder current = new StringBuilder();
                boolean first = true;
                for (String word : words) {
                    String testStripped = (current + (current.length() > 0 ? " " : "") + word).replaceAll("§.", "");
                    if (tr.getWidth(testStripped) > availWidth && current.length() > 0) {
                        LineType t = first ? type : (type == LineType.BULLET ? LineType.BULLET_CONT : LineType.NORMAL);
                        String lineStr = current.toString();
                        result.add(new OverlayLine(lineStr, t, indent, parseColorSegments(lineStr)));
                        current = new StringBuilder(word);
                        first = false;
                    } else {
                        if (current.length() > 0) current.append(" ");
                        current.append(word);
                    }
                }
                if (current.length() > 0) {
                    LineType t = first ? type : (type == LineType.BULLET ? LineType.BULLET_CONT : LineType.NORMAL);
                    String lineStr = current.toString();
                    result.add(new OverlayLine(lineStr, t, indent, parseColorSegments(lineStr)));
                }
            }
        }

        processedLines = result;
    }

    /**
     * Parse a string with § color codes into colored segments.
     */
    private static List<ColorSegment> parseColorSegments(String text) {
        List<ColorSegment> segments = new ArrayList<>();
        int currentColor = COLOR_BODY; // default
        StringBuilder current = new StringBuilder();

        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (c == '§' && i + 1 < text.length()) {
                // Flush current segment
                if (current.length() > 0) {
                    segments.add(new ColorSegment(current.toString(), currentColor));
                    current = new StringBuilder();
                }
                char code = text.charAt(i + 1);
                int newColor = colorForCode(code);
                if (newColor != -1) {
                    currentColor = newColor;
                } else if (code == 'r') {
                    currentColor = COLOR_BODY; // reset
                }
                i++; // skip the code char
            } else {
                current.append(c);
            }
        }
        if (current.length() > 0) {
            segments.add(new ColorSegment(current.toString(), currentColor));
        }
        return segments;
    }

    private static int colorForCode(char code) {
        return switch (code) {
            case '0' -> COLOR_BLACK;
            case '1' -> COLOR_DARK_BLUE;
            case '2' -> COLOR_DARK_GREEN;
            case '3' -> COLOR_DARK_AQUA;
            case '4' -> COLOR_DARK_RED;
            case '5' -> COLOR_DARK_PURPLE;
            case '6' -> COLOR_GOLD;
            case '7' -> COLOR_GRAY;
            case '8' -> COLOR_DARK_GRAY;
            case '9' -> COLOR_BLUE;
            case 'a' -> COLOR_GREEN;
            case 'b' -> COLOR_AQUA;
            case 'c' -> COLOR_RED;
            case 'd' -> COLOR_LIGHT_PURPLE;
            case 'e' -> COLOR_YELLOW;
            case 'f' -> COLOR_WHITE;
            default -> -1;
        };
    }

    @Override
    public void onHudRender(DrawContext context, RenderTickCounter tickCounter) {
        if (currentQuestion == null && !thinking) return;

        long now = System.currentTimeMillis();
        MinecraftClient client = MinecraftClient.getInstance();
        if (client == null) return;
        TextRenderer tr = client.textRenderer;
        int screenW = client.getWindow().getScaledWidth();

        String[] raw = rawLines;
        if (raw != null && (processedLines == null || processedFrom != raw)) {
            processLines(tr, raw);
            processedFrom = raw;
        }

        if (hideTime == 0 && processedLines != null) {
            if (now - showTime > DISPLAY_MS) hideTime = now;
        }

        float alpha;
        if (hideTime > 0) {
            float fadeOut = 1f - (float)(now - hideTime) / FADE_OUT_MS;
            if (fadeOut <= 0) { clear(); return; }
            alpha = fadeOut;
        } else {
            alpha = Math.min(1f, (float)(now - showTime) / FADE_IN_MS);
        }

        boolean hasQuestion = currentQuestion != null && !currentQuestion.isEmpty() && !thinking;
        int questionBarH = hasQuestion ? QUESTION_HEIGHT + 4 : 0;

        int[] hotm = hotmGrid;
        int hotmH = 0;
        if (hotm != null) {
            hotmH = 10 * (CELL_SIZE + CELL_GAP) + CELL_GAP + PADDING_Y + 10; // grid + label
        }

        int contentW, bodyH;
        if (thinking) {
            contentW = MIN_WIDTH;
            bodyH = PADDING_Y + LINE_HEIGHT + PADDING_Y;
        } else if (processedLines != null) {
            int maxLineW = 0;
            for (OverlayLine line : processedLines) {
                if (line.type != LineType.SPACER) {
                    String stripped = line.text.replaceAll("§.", "");
                    int w = tr.getWidth(stripped) + line.indent + 10;
                    if (w > maxLineW) maxLineW = w;
                }
            }
            if (hasQuestion) {
                int qw = tr.getWidth("> " + currentQuestion) + 10;
                if (qw > maxLineW) maxLineW = qw;
            }
            // HOTM grid needs at least 7*(CELL_SIZE+CELL_GAP)+CELL_GAP + PADDING*2
            int hotmMinW = hotm != null ? 7 * (CELL_SIZE + CELL_GAP) + CELL_GAP + PADDING_X * 2 : 0;
            contentW = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, Math.max(maxLineW + PADDING_X * 2, hotmMinW)));
            int linesH = 0;
            for (OverlayLine line : processedLines) {
                linesH += (line.type == LineType.SPACER) ? 6 : LINE_HEIGHT;
            }
            bodyH = PADDING_Y + linesH + PADDING_Y + hotmH;
        } else {
            return;
        }

        int totalH = HEADER_HEIGHT + 1 + questionBarH + bodyH;
        int x = screenW - contentW - MARGIN_RIGHT;
        int y = MARGIN_TOP;

        // === SHADOW ===
        for (int i = 4; i >= 1; i--) {
            int sa = (int)(((5 - i) * 12) * alpha);
            if (sa > 0) {
                fillRounded(context, x - i + 1, y - i + 2, contentW + (i - 1) * 2, totalH + (i - 1) * 2,
                        R + i - 1, (sa << 24));
            }
        }

        // === PANEL ===
        fillRounded(context, x, y, contentW, totalH, R, col(0xF0, 0x1A, 0x1A, 0x2E, alpha));

        // === HEADER ===
        int bandH = HEADER_HEIGHT / 3;
        fillRoundedTop(context, x, y, contentW, bandH, R, col(0xFF, 0x30, 0x30, 0x4A, alpha));
        fill(context, x, y + bandH, x + contentW, y + bandH * 2, col(0xFF, 0x2C, 0x2C, 0x44, alpha));
        fill(context, x, y + bandH * 2, x + contentW, y + HEADER_HEIGHT, col(0xFF, 0x28, 0x28, 0x40, alpha));

        // Top highlight
        fill(context, x + R, y, x + contentW - R, y + 1, col(0x44, 0x88, 0x88, 0xCC, alpha));

        // Accent line
        fill(context, x, y + HEADER_HEIGHT, x + contentW, y + HEADER_HEIGHT + 1, col(0xFF, 0x00, 0xBB, 0xEE, alpha));

        // === DOTS ===
        int dotCY = y + HEADER_HEIGHT / 2;
        int dotCX = x + 9;
        drawDot(context, dotCX, dotCY, 0xFF5F57, alpha);
        drawDot(context, dotCX + 8, dotCY, 0xFFBD2E, alpha);
        drawDot(context, dotCX + 16, dotCY, 0x28C840, alpha);

        // === TITLE ===
        int titleX = x + 9 + 24 + 4;
        context.drawText(tr, "SkyAI", titleX, y + (HEADER_HEIGHT - 8) / 2,
                withAlpha(0xFF00DDFF, alpha), false);

        String ver = "v" + HypixelAIUpdater.MOD_VERSION;
        int verW = tr.getWidth(ver);
        context.drawText(tr, ver, x + contentW - verW - PADDING_X, y + (HEADER_HEIGHT - 8) / 2,
                withAlpha(0xFF555566, alpha), false);

        // === QUESTION BAR ===
        int contentY = y + HEADER_HEIGHT + 1;
        if (hasQuestion) {
            fill(context, x, contentY, x + contentW, contentY + questionBarH,
                    col(0xFF, 0x1E, 0x1E, 0x30, alpha));
            fill(context, x + PADDING_X, contentY + questionBarH - 1,
                    x + contentW - PADDING_X, contentY + questionBarH,
                    col(0x33, 0x55, 0x55, 0x77, alpha));

            String qText = "> " + currentQuestion;
            if (tr.getWidth(qText) > contentW - PADDING_X * 2) {
                qText = qText.substring(0, Math.min(qText.length(), 35)) + "...";
            }
            context.drawText(tr, qText, x + PADDING_X, contentY + 3,
                    withAlpha(0xFF44AACC, alpha), false);
            contentY += questionBarH;
        }

        // === BODY ===
        int cy = contentY + PADDING_Y;

        if (thinking) {
            long dots = ((now - thinkingStart) / 400) % 4;
            String thinkText = "Thinking" + ".".repeat((int) dots);
            context.drawText(tr, thinkText, x + PADDING_X, cy, withAlpha(0xFF888899, alpha), false);
        } else if (processedLines != null) {
            int tx = x + PADDING_X;
            for (OverlayLine line : processedLines) {
                if (line.type == LineType.SPACER) { cy += 6; continue; }

                int lx = tx + line.indent;

                switch (line.type) {
                    case BULLET:
                        context.drawText(tr, "\u2022", tx + 2, cy, withAlpha(COLOR_GOLD, alpha), false);
                        drawColoredText(context, tr, line.segments, lx + 8, cy, alpha);
                        break;
                    case BULLET_CONT:
                        drawColoredText(context, tr, line.segments, lx + 8, cy, alpha);
                        break;
                    case NUMBERED:
                        // Find the "N." prefix
                        String stripped = line.text.replaceAll("§.", "");
                        int dotIdx = stripped.indexOf('.');
                        if (dotIdx > 0 && dotIdx < 4) {
                            String num = stripped.substring(0, dotIdx + 1);
                            context.drawText(tr, num, lx, cy, withAlpha(COLOR_AQUA, alpha), false);
                            // Draw the rest with color segments, offset past the number
                            int numW = tr.getWidth(num + " ");
                            // Re-parse segments without the number prefix
                            String rest = line.text;
                            int realDot = rest.replaceAll("§.", "").indexOf('.');
                            if (realDot >= 0) {
                                // Find actual position in original string accounting for color codes
                                int pos = 0, stripped_pos = 0;
                                while (pos < rest.length() && stripped_pos <= realDot) {
                                    if (rest.charAt(pos) == '§' && pos + 1 < rest.length()) {
                                        pos += 2;
                                    } else {
                                        stripped_pos++;
                                        pos++;
                                    }
                                }
                                // Skip whitespace after the dot
                                while (pos < rest.length() && rest.charAt(pos) == ' ') pos++;
                                String afterNum = rest.substring(pos);
                                drawColoredText(context, tr, parseColorSegments(afterNum), lx + numW, cy, alpha);
                            }
                        } else {
                            drawColoredText(context, tr, line.segments, lx, cy, alpha);
                        }
                        break;
                    default:
                        drawColoredText(context, tr, line.segments, lx, cy, alpha);
                        break;
                }
                cy += LINE_HEIGHT;
            }
        }

        // === HOTM PIXEL ART GRID ===
        if (hotm != null && !thinking) {
            drawHotmGrid(context, tr, hotm, x, cy + 4, contentW, alpha);
        }

        // Bottom edge
        fill(context, x + R, y + totalH - 1, x + contentW - R, y + totalH,
                col(0x22, 0x00, 0x00, 0x00, alpha));
    }

    /**
     * Draw text with color segments.
     */
    private static void drawColoredText(DrawContext ctx, TextRenderer tr,
                                         List<ColorSegment> segments, int x, int y, float alpha) {
        if (segments == null) return;
        int cx = x;
        for (ColorSegment seg : segments) {
            ctx.drawText(tr, seg.text, cx, y, withAlpha(seg.color, alpha), false);
            cx += tr.getWidth(seg.text);
        }
    }

    /**
     * Draw the HOTM tree as a pixel art grid.
     * Each cell is a colored square representing a perk's state.
     * Grid is 7 cols x 10 rows, displayed top (T10) to bottom (T1).
     */
    private static void drawHotmGrid(DrawContext ctx, TextRenderer tr,
                                      int[] grid, int panelX, int startY, int panelW, float alpha) {
        int gridW = 7 * (CELL_SIZE + CELL_GAP) + CELL_GAP;
        int gridX = panelX + (panelW - gridW) / 2; // center the grid

        // Label
        ctx.drawText(tr, "HotM Tree", gridX, startY, withAlpha(COLOR_GOLD, alpha), false);
        int gy = startY + 10;

        // Separator
        fill(ctx, panelX + PADDING_X, gy - 2, panelX + panelW - PADDING_X, gy - 1,
                col(0x33, 0x55, 0x55, 0x77, alpha));

        // Draw grid background
        fill(ctx, gridX - 1, gy - 1, gridX + gridW + 1, gy + 10 * (CELL_SIZE + CELL_GAP) + CELL_GAP + 1,
                col(0xFF, 0x12, 0x12, 0x1C, alpha));

        // Draw cells — tier 10 at top, tier 1 at bottom
        for (int row = 0; row < 10; row++) {
            int tier = 9 - row; // tier 9 = T10 at top, tier 0 = T1 at bottom
            for (int c = 0; c < 7; c++) {
                int state = grid[tier * 7 + c];
                if (state == 0) continue; // empty slot

                int cx = gridX + CELL_GAP + c * (CELL_SIZE + CELL_GAP);
                int cy = gy + CELL_GAP + row * (CELL_SIZE + CELL_GAP);

                int cellColor;
                switch (state) {
                    case -1: cellColor = col(0xFF, 0x33, 0x33, 0x33, alpha); break; // locked — dark
                    case 1:  cellColor = col(0xFF, 0x55, 0x55, 0x55, alpha); break; // unlocked, 0 — gray
                    case 2:  cellColor = col(0xFF, 0xFF, 0xAA, 0x00, alpha); break; // partial — gold
                    case 3:  cellColor = col(0xFF, 0x55, 0xFF, 0x55, alpha); break; // maxed — green
                    case 4:  cellColor = col(0xFF, 0x55, 0xFF, 0xFF, alpha); break; // ability — aqua
                    case 5:  cellColor = col(0xFF, 0xFF, 0x55, 0xFF, alpha); break; // active ability — pink
                    default: cellColor = col(0xFF, 0x44, 0x44, 0x44, alpha); break;
                }

                fill(ctx, cx, cy, cx + CELL_SIZE, cy + CELL_SIZE, cellColor);

                // Inner highlight (top-left 1px lighter)
                if (state > 0) {
                    int highlight = col(0x33, 0xFF, 0xFF, 0xFF, alpha);
                    fill(ctx, cx, cy, cx + CELL_SIZE, cy + 1, highlight);
                    fill(ctx, cx, cy, cx + 1, cy + CELL_SIZE, highlight);
                }
            }
        }

        // Legend below grid
        int legendY = gy + 10 * (CELL_SIZE + CELL_GAP) + CELL_GAP + 3;
        int lx = gridX;
        lx = drawLegendItem(ctx, tr, lx, legendY, col(0xFF, 0x55, 0xFF, 0x55, alpha), "Max", alpha);
        lx = drawLegendItem(ctx, tr, lx + 4, legendY, col(0xFF, 0xFF, 0xAA, 0x00, alpha), "Lvl'd", alpha);
        lx = drawLegendItem(ctx, tr, lx + 4, legendY, col(0xFF, 0x55, 0x55, 0x55, alpha), "0", alpha);
        drawLegendItem(ctx, tr, lx + 4, legendY, col(0xFF, 0x33, 0x33, 0x33, alpha), "Lock", alpha);
    }

    private static int drawLegendItem(DrawContext ctx, TextRenderer tr,
                                       int x, int y, int color, String label, float alpha) {
        fill(ctx, x, y + 1, x + 4, y + 5, color);
        ctx.drawText(tr, label, x + 6, y, withAlpha(COLOR_GRAY, alpha), false);
        return x + 6 + tr.getWidth(label);
    }

    // --- Drawing helpers ---

    private static void drawDot(DrawContext ctx, int cx, int cy, int rgb, float alpha) {
        int c = col(0xFF, (rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF, alpha);
        fill(ctx, cx - 1, cy - 2, cx + 2, cy + 3, c);
        fill(ctx, cx - 2, cy - 1, cx + 3, cy + 2, c);
    }

    private static void fillRounded(DrawContext ctx, int x, int y, int w, int h, int r, int color) {
        if (h <= 0 || w <= 0) return;
        int[] insets = r >= 3 ? new int[]{3, 1, 1} : r >= 2 ? new int[]{2, 1} : new int[]{1};

        for (int i = 0; i < insets.length && i < h; i++)
            fill(ctx, x + insets[i], y + i, x + w - insets[i], y + i + 1, color);

        int midStart = Math.min(insets.length, h);
        int midEnd = Math.max(midStart, h - insets.length);
        if (midEnd > midStart)
            fill(ctx, x, y + midStart, x + w, y + midEnd, color);

        for (int i = 0; i < insets.length && (h - 1 - i) >= midEnd; i++)
            fill(ctx, x + insets[i], y + h - 1 - i, x + w - insets[i], y + h - i, color);
    }

    private static void fillRoundedTop(DrawContext ctx, int x, int y, int w, int h, int r, int color) {
        if (h <= 0 || w <= 0) return;
        int[] insets = r >= 3 ? new int[]{3, 1, 1} : r >= 2 ? new int[]{2, 1} : new int[]{1};

        for (int i = 0; i < insets.length && i < h; i++)
            fill(ctx, x + insets[i], y + i, x + w - insets[i], y + i + 1, color);

        int midStart = Math.min(insets.length, h);
        if (h > midStart)
            fill(ctx, x, y + midStart, x + w, y + h, color);
    }

    private static void fill(DrawContext ctx, int x1, int y1, int x2, int y2, int argb) {
        if (((argb >> 24) & 0xFF) <= 0) return;
        ctx.fill(x1, y1, x2, y2, argb);
    }

    private static int col(int a, int r, int g, int b, float alpha) {
        return ((int)(a * alpha) << 24) | (r << 16) | (g << 8) | b;
    }

    private static int withAlpha(int argb, float alpha) {
        int a = (int)(((argb >> 24) & 0xFF) * alpha);
        return (a << 24) | (argb & 0x00FFFFFF);
    }

    private enum LineType { NORMAL, BULLET, BULLET_CONT, NUMBERED, SPACER }

    private static class ColorSegment {
        final String text;
        final int color;
        ColorSegment(String text, int color) {
            this.text = text;
            this.color = color;
        }
    }

    private static class OverlayLine {
        final String text;
        final LineType type;
        final int indent;
        final List<ColorSegment> segments;
        OverlayLine(String text, LineType type, int indent, List<ColorSegment> segments) {
            this.text = text;
            this.type = type;
            this.indent = indent;
            this.segments = segments;
        }
    }
}
