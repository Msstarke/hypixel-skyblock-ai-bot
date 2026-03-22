package com.hypixelai;

import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.render.RenderTickCounter;

import java.util.ArrayList;
import java.util.List;

/**
 * Polished floating HUD overlay for AI responses.
 * Supports § color codes, pixel art HOTM grid with text-wrap layout.
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
    private static final int MAX_WIDTH_HOTM = 340; // wider when HOTM grid is shown
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
    private static final int CELL_SIZE = 8;
    private static final int CELL_GAP = 1;
    // Grid dimensions
    private static final int GRID_COLS = 7;
    private static final int GRID_ROWS = 10;
    private static final int GRID_W = GRID_COLS * (CELL_SIZE + CELL_GAP) + CELL_GAP; // 64
    private static final int GRID_H = GRID_ROWS * (CELL_SIZE + CELL_GAP) + CELL_GAP; // 91
    // HOTM panel (grid + title + legend + padding)
    private static final int HOTM_PANEL_PAD = 6;
    private static final int HOTM_TITLE_H = 10;
    private static final int HOTM_LEGEND_H = 10;
    private static final int HOTM_PANEL_W = GRID_W + HOTM_PANEL_PAD * 2;
    private static final int HOTM_PANEL_H = HOTM_TITLE_H + 2 + GRID_H + 4 + HOTM_LEGEND_H + HOTM_PANEL_PAD * 2;

    // Feedback bar
    private static final int FEEDBACK_BAR_H = 14;

    // State (set from any thread)
    private static volatile String currentQuestion = null;
    private static volatile String[] rawLines = null;
    private static volatile int[] hotmGrid = null;
    private static volatile boolean thinking = false;
    private static volatile long showTime = 0;
    private static volatile long hideTime = 0;
    private static volatile long thinkingStart = 0;

    // Feedback state
    private static volatile String feedbackVote = null; // "up", "down", or null
    private static volatile String lastQuestion = null;
    private static volatile String lastResponse = null;

    // Processed lines for narrow zone (beside grid) and full zone (below grid)
    private static List<OverlayLine> narrowLines = null;
    private static List<OverlayLine> fullLines = null;
    // When no HOTM, all lines go here
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
        narrowLines = null;
        fullLines = null;
        processedFrom = null;
        showTime = System.currentTimeMillis();
        hideTime = 0;
        thinking = false;
        feedbackVote = null;
        lastQuestion = question;
        lastResponse = responseLines != null ? String.join("\n", responseLines) : "";
    }

    public static void showThinking(String question) {
        currentQuestion = question;
        rawLines = null;
        processedLines = null;
        narrowLines = null;
        fullLines = null;
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
        narrowLines = null;
        fullLines = null;
        processedFrom = null;
        thinking = false;
        showTime = 0;
        hideTime = 0;
    }

    public static void setFeedback(String vote) {
        feedbackVote = vote;
        // Reset display timer so it doesn't fade while showing feedback
        showTime = System.currentTimeMillis();
        hideTime = 0;
    }

    public static String getLastQuestion() { return lastQuestion; }
    public static String getLastResponse() { return lastResponse; }
    public static boolean hasPendingFeedback() { return feedbackVote == null && lastResponse != null && rawLines != null; }

    public static void register() {
        HudRenderCallback.EVENT.register(new SkyAIOverlay());
    }

    /**
     * Process lines with text-wrap layout when HOTM grid is present.
     * Lines beside the grid use a narrow wrap width; lines below use full width.
     */
    private static void processLinesWithHotm(TextRenderer tr, String[] lines, int panelW) {
        int fullWrap = panelW - PADDING_X * 2;
        int narrowWrap = panelW - PADDING_X * 2 - HOTM_PANEL_W - 8; // 8px gap between text and grid panel

        // How many text line slots fit beside the HOTM panel
        int hotmPanelLines = HOTM_PANEL_H / LINE_HEIGHT + 1;

        List<OverlayLine> narrow = new ArrayList<>();
        List<OverlayLine> full = new ArrayList<>();

        // Process all raw lines, distributing to narrow vs full
        List<OverlayLine> allWrapped = new ArrayList<>();
        for (String line : lines) {
            if (line.isEmpty()) {
                allWrapped.add(new OverlayLine("", LineType.SPACER, 0, null));
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

            // First wrap at narrow width, then once we overflow we'll re-wrap at full width
            wrapLine(tr, content, type, indent, narrowWrap, allWrapped);
        }

        // Split: first hotmPanelLines go to narrow, rest to full
        for (int i = 0; i < allWrapped.size(); i++) {
            if (i < hotmPanelLines) {
                narrow.add(allWrapped.get(i));
            } else {
                full.add(allWrapped.get(i));
            }
        }

        // If there are leftover lines for the full section, re-wrap them at full width
        // Actually we already wrapped at narrow, which works fine for full too (just shorter lines)
        // But for cleaner look, let's keep them as-is since narrow wrap is subset of full

        narrowLines = narrow;
        fullLines = full;
    }

    private static void processLinesNormal(TextRenderer tr, String[] lines, int panelW) {
        int wrapWidth = panelW - PADDING_X * 2;
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
            wrapLine(tr, content, type, indent, wrapWidth, result);
        }
        processedLines = result;
    }

    private static void wrapLine(TextRenderer tr, String content, LineType type, int indent,
                                  int wrapWidth, List<OverlayLine> out) {
        String stripped = content.replaceAll("§.", "");
        int availWidth = wrapWidth - indent;
        if (tr.getWidth(stripped) <= availWidth) {
            out.add(new OverlayLine(content, type, indent, parseColorSegments(content)));
        } else {
            String[] words = content.split(" ");
            StringBuilder current = new StringBuilder();
            boolean first = true;
            for (String word : words) {
                String testStripped = (current + (current.length() > 0 ? " " : "") + word).replaceAll("§.", "");
                if (tr.getWidth(testStripped) > availWidth && current.length() > 0) {
                    LineType t = first ? type : (type == LineType.BULLET ? LineType.BULLET_CONT : LineType.NORMAL);
                    String lineStr = current.toString();
                    out.add(new OverlayLine(lineStr, t, indent, parseColorSegments(lineStr)));
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
                out.add(new OverlayLine(lineStr, t, indent, parseColorSegments(lineStr)));
            }
        }
    }

    private static List<ColorSegment> parseColorSegments(String text) {
        List<ColorSegment> segments = new ArrayList<>();
        int currentColor = COLOR_BODY;
        StringBuilder current = new StringBuilder();
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (c == '§' && i + 1 < text.length()) {
                if (current.length() > 0) {
                    segments.add(new ColorSegment(current.toString(), currentColor));
                    current = new StringBuilder();
                }
                char code = text.charAt(i + 1);
                int newColor = colorForCode(code);
                if (newColor != -1) {
                    currentColor = newColor;
                } else if (code == 'r') {
                    currentColor = COLOR_BODY;
                }
                i++;
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
        int[] hotm = hotmGrid;
        boolean hasHotm = hotm != null;

        int maxW = hasHotm ? MAX_WIDTH_HOTM : MAX_WIDTH;

        if (raw != null && (processedFrom != raw)) {
            if (hasHotm) {
                // Calculate panel width first for wrapping
                int tempW = Math.min(maxW, Math.max(MIN_WIDTH, HOTM_PANEL_W + PADDING_X * 2 + 100));
                // Measure actual text width needed
                int maxLineW = 0;
                for (String line : raw) {
                    String stripped = line.replaceAll("§.", "");
                    int w = tr.getWidth(stripped) + 20;
                    if (w > maxLineW) maxLineW = w;
                }
                tempW = Math.min(maxW, Math.max(tempW, maxLineW + HOTM_PANEL_W + PADDING_X * 2 + 8));
                processLinesWithHotm(tr, raw, tempW);
            } else {
                processLinesNormal(tr, raw, maxW);
            }
            processedFrom = raw;
        }

        if (hideTime == 0 && (processedLines != null || narrowLines != null)) {
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

        // Calculate dimensions
        int contentW, bodyH;
        if (thinking) {
            contentW = MIN_WIDTH;
            bodyH = PADDING_Y + LINE_HEIGHT + PADDING_Y;
        } else if (hasHotm && narrowLines != null) {
            // Side-by-side layout
            int narrowH = 0;
            for (OverlayLine line : narrowLines) {
                narrowH += (line.type == LineType.SPACER) ? 6 : LINE_HEIGHT;
            }
            int fullH = 0;
            if (fullLines != null) {
                for (OverlayLine line : fullLines) {
                    fullH += (line.type == LineType.SPACER) ? 6 : LINE_HEIGHT;
                }
            }
            // Body height = max of (narrow text height, HOTM panel height) + full text below
            int sideH = Math.max(narrowH, HOTM_PANEL_H);
            bodyH = PADDING_Y + sideH + (fullH > 0 ? 6 + fullH : 0) + PADDING_Y;

            // Content width
            int maxLineW = 0;
            for (OverlayLine line : narrowLines) {
                if (line.type != LineType.SPACER) {
                    String stripped = line.text.replaceAll("§.", "");
                    int w = tr.getWidth(stripped) + line.indent + 10;
                    if (w > maxLineW) maxLineW = w;
                }
            }
            if (fullLines != null) {
                for (OverlayLine line : fullLines) {
                    if (line.type != LineType.SPACER) {
                        String stripped = line.text.replaceAll("§.", "");
                        int w = tr.getWidth(stripped) + line.indent + 10;
                        if (w > maxLineW) maxLineW = w;
                    }
                }
            }
            if (hasQuestion) {
                int qw = tr.getWidth("> " + currentQuestion) + 10;
                if (qw > maxLineW) maxLineW = qw;
            }
            contentW = Math.min(maxW, Math.max(MIN_WIDTH,
                    Math.max(maxLineW + HOTM_PANEL_W + PADDING_X * 2 + 8, HOTM_PANEL_W + PADDING_X * 2 + 80)));
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
            contentW = Math.min(maxW, Math.max(MIN_WIDTH, maxLineW + PADDING_X * 2));
            int linesH = 0;
            for (OverlayLine line : processedLines) {
                linesH += (line.type == LineType.SPACER) ? 6 : LINE_HEIGHT;
            }
            bodyH = PADDING_Y + linesH + PADDING_Y;
        } else {
            return;
        }

        // Feedback bar (only when response is shown and not thinking)
        boolean showFeedback = !thinking && rawLines != null;
        int feedbackH = showFeedback ? FEEDBACK_BAR_H : 0;

        int totalH = HEADER_HEIGHT + 1 + questionBarH + bodyH + feedbackH;
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
                qText = qText.substring(0, Math.min(qText.length(), 40)) + "...";
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
        } else if (hasHotm && narrowLines != null) {
            // === SIDE-BY-SIDE LAYOUT ===
            int textX = x + PADDING_X;
            int hotmPanelX = x + contentW - PADDING_X - HOTM_PANEL_W;
            int hotmPanelY = cy;

            // Draw HOTM panel (right side)
            drawHotmPanel(context, tr, hotm, hotmPanelX, hotmPanelY, alpha);

            // Draw narrow text lines (left side, beside the grid)
            int textCy = cy;
            for (OverlayLine line : narrowLines) {
                if (line.type == LineType.SPACER) { textCy += 6; continue; }
                drawLine(context, tr, line, textX, textCy, alpha);
                textCy += LINE_HEIGHT;
            }

            // Move past the HOTM panel
            cy = hotmPanelY + HOTM_PANEL_H + 6;

            // Draw full-width text lines (below the grid)
            if (fullLines != null) {
                for (OverlayLine line : fullLines) {
                    if (line.type == LineType.SPACER) { cy += 6; continue; }
                    drawLine(context, tr, line, textX, cy, alpha);
                    cy += LINE_HEIGHT;
                }
            }
        } else if (processedLines != null) {
            int tx = x + PADDING_X;
            for (OverlayLine line : processedLines) {
                if (line.type == LineType.SPACER) { cy += 6; continue; }
                drawLine(context, tr, line, tx, cy, alpha);
                cy += LINE_HEIGHT;
            }
        }

        // === FEEDBACK BAR ===
        if (showFeedback) {
            int fbY = y + totalH - feedbackH;

            // Separator line
            fill(context, x + PADDING_X, fbY, x + contentW - PADDING_X, fbY + 1,
                    col(0x33, 0x55, 0x55, 0x77, alpha));

            if (feedbackVote != null) {
                // Already voted — show confirmation
                String msg = feedbackVote.equals("up") ? "\u2714 Thanks for the feedback!" : "\u2716 Noted — we'll improve!";
                int msgColor = feedbackVote.equals("up") ? COLOR_GREEN : COLOR_GOLD;
                int msgW = tr.getWidth(msg);
                context.drawText(tr, msg, x + (contentW - msgW) / 2, fbY + 3,
                        withAlpha(msgColor, alpha), false);
            } else {
                // Show vote prompt
                String correctLabel = "\u2714 !correct";
                String wrongLabel = "\u2716 !wrong";
                int correctW = tr.getWidth(correctLabel);
                int wrongW = tr.getWidth(wrongLabel);
                int gap = 16;
                int totalBtnW = correctW + gap + wrongW;
                int btnX = x + (contentW - totalBtnW) / 2;

                // Correct button
                int correctBgX = btnX - 3;
                int correctBgW = correctW + 6;
                fillRounded(context, correctBgX, fbY + 1, correctBgW, FEEDBACK_BAR_H - 2, 1,
                        col(0x44, 0x22, 0x88, 0x22, alpha));
                context.drawText(tr, correctLabel, btnX, fbY + 3,
                        withAlpha(COLOR_GREEN, alpha), false);

                // Wrong button
                int wrongX = btnX + correctW + gap;
                int wrongBgX = wrongX - 3;
                int wrongBgW = wrongW + 6;
                fillRounded(context, wrongBgX, fbY + 1, wrongBgW, FEEDBACK_BAR_H - 2, 1,
                        col(0x44, 0x88, 0x22, 0x22, alpha));
                context.drawText(tr, wrongLabel, wrongX, fbY + 3,
                        withAlpha(COLOR_RED, alpha), false);
            }
        }

        // Bottom edge
        fill(context, x + R, y + totalH - 1, x + contentW - R, y + totalH,
                col(0x22, 0x00, 0x00, 0x00, alpha));
    }

    /**
     * Draw a single text line (handles bullet, numbered, normal types).
     */
    private static void drawLine(DrawContext ctx, TextRenderer tr, OverlayLine line, int tx, int cy, float alpha) {
        int lx = tx + line.indent;
        switch (line.type) {
            case BULLET:
                ctx.drawText(tr, "\u2022", tx + 2, cy, withAlpha(COLOR_GOLD, alpha), false);
                drawColoredText(ctx, tr, line.segments, lx + 8, cy, alpha);
                break;
            case BULLET_CONT:
                drawColoredText(ctx, tr, line.segments, lx + 8, cy, alpha);
                break;
            case NUMBERED:
                String stripped = line.text.replaceAll("§.", "");
                int dotIdx = stripped.indexOf('.');
                if (dotIdx > 0 && dotIdx < 4) {
                    String num = stripped.substring(0, dotIdx + 1);
                    ctx.drawText(tr, num, lx, cy, withAlpha(COLOR_AQUA, alpha), false);
                    int numW = tr.getWidth(num + " ");
                    String rest = line.text;
                    int realDot = rest.replaceAll("§.", "").indexOf('.');
                    if (realDot >= 0) {
                        int pos = 0, stripped_pos = 0;
                        while (pos < rest.length() && stripped_pos <= realDot) {
                            if (rest.charAt(pos) == '§' && pos + 1 < rest.length()) {
                                pos += 2;
                            } else {
                                stripped_pos++;
                                pos++;
                            }
                        }
                        while (pos < rest.length() && rest.charAt(pos) == ' ') pos++;
                        String afterNum = rest.substring(pos);
                        drawColoredText(ctx, tr, parseColorSegments(afterNum), lx + numW, cy, alpha);
                    }
                } else {
                    drawColoredText(ctx, tr, line.segments, lx, cy, alpha);
                }
                break;
            default:
                drawColoredText(ctx, tr, line.segments, lx, cy, alpha);
                break;
        }
    }

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
     * Draw the HOTM grid inside a styled panel with title and legend.
     */
    private static void drawHotmPanel(DrawContext ctx, TextRenderer tr,
                                       int[] grid, int px, int py, float alpha) {
        // Panel background (darker inset)
        fillRounded(ctx, px, py, HOTM_PANEL_W, HOTM_PANEL_H, 2,
                col(0xFF, 0x12, 0x12, 0x1E, alpha));

        // Border
        int borderC = col(0x55, 0x44, 0x44, 0x66, alpha);
        fill(ctx, px, py, px + HOTM_PANEL_W, py + 1, borderC); // top
        fill(ctx, px, py + HOTM_PANEL_H - 1, px + HOTM_PANEL_W, py + HOTM_PANEL_H, borderC); // bottom
        fill(ctx, px, py, px + 1, py + HOTM_PANEL_H, borderC); // left
        fill(ctx, px + HOTM_PANEL_W - 1, py, px + HOTM_PANEL_W, py + HOTM_PANEL_H, borderC); // right

        int innerX = px + HOTM_PANEL_PAD;
        int innerY = py + HOTM_PANEL_PAD;

        // Title
        String title = "HotM Tree";
        int titleW = tr.getWidth(title);
        ctx.drawText(tr, title, innerX + (GRID_W - titleW) / 2, innerY,
                withAlpha(COLOR_GOLD, alpha), false);

        int gridY = innerY + HOTM_TITLE_H + 2;

        // Grid background
        fill(ctx, innerX - 1, gridY - 1, innerX + GRID_W + 1, gridY + GRID_H + 1,
                col(0xFF, 0x0E, 0x0E, 0x16, alpha));

        // Draw cells — tier 10 at top, tier 1 at bottom
        for (int row = 0; row < GRID_ROWS; row++) {
            int tier = 9 - row;
            for (int c = 0; c < GRID_COLS; c++) {
                int state = grid[tier * 7 + c];
                if (state == 0) continue;

                int cx = innerX + CELL_GAP + c * (CELL_SIZE + CELL_GAP);
                int cy = gridY + CELL_GAP + row * (CELL_SIZE + CELL_GAP);

                int cellColor;
                switch (state) {
                    case -1: cellColor = col(0xFF, 0x33, 0x33, 0x33, alpha); break;
                    case 1:  cellColor = col(0xFF, 0x55, 0x55, 0x55, alpha); break;
                    case 2:  cellColor = col(0xFF, 0xFF, 0xAA, 0x00, alpha); break;
                    case 3:  cellColor = col(0xFF, 0x55, 0xFF, 0x55, alpha); break;
                    case 4:  cellColor = col(0xFF, 0x55, 0xFF, 0xFF, alpha); break;
                    case 5:  cellColor = col(0xFF, 0xFF, 0x55, 0xFF, alpha); break;
                    default: cellColor = col(0xFF, 0x44, 0x44, 0x44, alpha); break;
                }

                fill(ctx, cx, cy, cx + CELL_SIZE, cy + CELL_SIZE, cellColor);

                // Inner highlight
                if (state > 0) {
                    int hl = col(0x33, 0xFF, 0xFF, 0xFF, alpha);
                    fill(ctx, cx, cy, cx + CELL_SIZE, cy + 1, hl);
                    fill(ctx, cx, cy, cx + 1, cy + CELL_SIZE, hl);
                }
            }
        }

        // Legend — compact, below grid
        int legendY = gridY + GRID_H + 4;
        int lx = innerX;
        lx = drawLegendItem(ctx, tr, lx, legendY, col(0xFF, 0x55, 0xFF, 0x55, alpha), "M", alpha);
        lx = drawLegendItem(ctx, tr, lx + 2, legendY, col(0xFF, 0xFF, 0xAA, 0x00, alpha), "L", alpha);
        lx = drawLegendItem(ctx, tr, lx + 2, legendY, col(0xFF, 0x55, 0x55, 0x55, alpha), "0", alpha);
        drawLegendItem(ctx, tr, lx + 2, legendY, col(0xFF, 0x33, 0x33, 0x33, alpha), "\u2716", alpha);
    }

    private static int drawLegendItem(DrawContext ctx, TextRenderer tr,
                                       int x, int y, int color, String label, float alpha) {
        fill(ctx, x, y + 1, x + 4, y + 5, color);
        ctx.drawText(tr, label, x + 5, y, withAlpha(COLOR_GRAY, alpha), false);
        return x + 5 + tr.getWidth(label);
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
