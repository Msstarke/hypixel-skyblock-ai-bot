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
 * NanoVG rendered shapes (shadow, panel, header, grid) + MC TextRenderer for text.
 * Supports section color codes, pixel art HOTM grid with text-wrap layout.
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
    private static final int MAX_WIDTH_HOTM = 340;
    private static final int MIN_WIDTH = 180;
    private static final int R = 6; // corner radius (bumped from 3 for NVG)

    // Color map for section codes
    private static final int COLOR_BLACK       = 0xFF000000;
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

    // HOTM grid
    private static final int CELL_SIZE = 8;
    private static final int CELL_GAP = 1;
    private static final int GRID_COLS = 7;
    private static final int GRID_ROWS = 10;
    private static final int GRID_W = GRID_COLS * (CELL_SIZE + CELL_GAP) + CELL_GAP;
    private static final int GRID_H = GRID_ROWS * (CELL_SIZE + CELL_GAP) + CELL_GAP;
    private static final int HOTM_PANEL_PAD = 6;
    private static final int HOTM_TITLE_H = 10;
    private static final int HOTM_LEGEND_H = 10;
    private static final int HOTM_PANEL_W = GRID_W + HOTM_PANEL_PAD * 2;
    private static final int HOTM_PANEL_H = HOTM_TITLE_H + 2 + GRID_H + 4 + HOTM_LEGEND_H + HOTM_PANEL_PAD * 2;

    private static final int FEEDBACK_BAR_H = 14;

    // State
    private static volatile String currentQuestion = null;
    private static volatile String[] rawLines = null;
    private static volatile int[] hotmGrid = null;
    private static volatile boolean thinking = false;
    private static volatile long showTime = 0;
    private static volatile long hideTime = 0;
    private static volatile long thinkingStart = 0;

    // Feedback
    private static volatile String feedbackVote = null;
    private static volatile String lastQuestion = null;
    private static volatile String lastResponse = null;

    // Processed lines
    private static List<OverlayLine> narrowLines = null;
    private static List<OverlayLine> fullLines = null;
    private static List<OverlayLine> processedLines = null;
    private static String[] processedFrom = null;

    private static final long FADE_IN_MS = 200;
    private static final long DISPLAY_MS = 30000;
    private static final long FADE_OUT_MS = 500;

    // ===================== Public API =====================

    public static void show(String question, String[] responseLines) {
        show(question, responseLines, null);
    }

    public static void show(String question, String[] responseLines, int[] hotmData) {
        currentQuestion = question;
        rawLines = responseLines;
        hotmGrid = hotmData;
        processedLines = null; narrowLines = null; fullLines = null; processedFrom = null;
        showTime = System.currentTimeMillis();
        hideTime = 0; thinking = false; feedbackVote = null;
        lastQuestion = question;
        lastResponse = responseLines != null ? String.join("\n", responseLines) : "";
    }

    public static void showThinking(String question) {
        currentQuestion = question; rawLines = null;
        processedLines = null; narrowLines = null; fullLines = null; processedFrom = null;
        thinking = true; thinkingStart = System.currentTimeMillis();
        showTime = System.currentTimeMillis(); hideTime = 0;
    }

    public static void hide() {
        if (hideTime == 0 && (rawLines != null || thinking)) hideTime = System.currentTimeMillis();
    }

    public static void clear() {
        currentQuestion = null; rawLines = null; hotmGrid = null;
        processedLines = null; narrowLines = null; fullLines = null; processedFrom = null;
        thinking = false; showTime = 0; hideTime = 0;
    }

    public static void setFeedback(String vote) {
        feedbackVote = vote;
        showTime = System.currentTimeMillis(); hideTime = 0;
    }

    public static String getLastQuestion() { return lastQuestion; }
    public static String getLastResponse() { return lastResponse; }
    public static boolean hasPendingFeedback() { return feedbackVote == null && lastResponse != null && rawLines != null; }

    public static void register() {
        HudRenderCallback.EVENT.register(new SkyAIOverlay());
    }

    // ===================== Render =====================

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

        // Process lines if needed
        if (raw != null && processedFrom != raw) {
            if (hasHotm) {
                int tempW = Math.min(maxW, Math.max(MIN_WIDTH, HOTM_PANEL_W + PADDING_X * 2 + 100));
                int maxLineW = 0;
                for (String line : raw) {
                    int w = tr.getWidth(line.replaceAll("\u00a7.", "")) + 20;
                    if (w > maxLineW) maxLineW = w;
                }
                tempW = Math.min(maxW, Math.max(tempW, maxLineW + HOTM_PANEL_W + PADDING_X * 2 + 8));
                processLinesWithHotm(tr, raw, tempW);
            } else {
                processLinesNormal(tr, raw, maxW);
            }
            processedFrom = raw;
        }

        // Auto-hide timer
        if (hideTime == 0 && (processedLines != null || narrowLines != null)) {
            if (now - showTime > DISPLAY_MS) hideTime = now;
        }

        // Alpha (fade in/out)
        float alpha;
        if (hideTime > 0) {
            float fadeOut = 1f - (float) (now - hideTime) / FADE_OUT_MS;
            if (fadeOut <= 0) { clear(); return; }
            alpha = fadeOut;
        } else {
            alpha = Math.min(1f, (float) (now - showTime) / FADE_IN_MS);
        }

        boolean hasQuestion = currentQuestion != null && !currentQuestion.isEmpty() && !thinking;
        int questionBarH = hasQuestion ? QUESTION_HEIGHT + 4 : 0;

        // ===== Calculate dimensions =====
        int contentW, bodyH;
        if (thinking) {
            contentW = MIN_WIDTH;
            bodyH = PADDING_Y + LINE_HEIGHT + PADDING_Y;
        } else if (hasHotm && narrowLines != null) {
            int narrowH = 0;
            for (OverlayLine l : narrowLines) narrowH += (l.type == LineType.SPACER) ? 6 : LINE_HEIGHT;
            int fullH = 0;
            if (fullLines != null) for (OverlayLine l : fullLines) fullH += (l.type == LineType.SPACER) ? 6 : LINE_HEIGHT;
            int sideH = Math.max(narrowH, HOTM_PANEL_H);
            bodyH = PADDING_Y + sideH + (fullH > 0 ? 6 + fullH : 0) + PADDING_Y;
            int maxLineW = measureMaxLineWidth(tr, narrowLines, fullLines, hasQuestion ? currentQuestion : null);
            contentW = Math.min(maxW, Math.max(MIN_WIDTH,
                    Math.max(maxLineW + HOTM_PANEL_W + PADDING_X * 2 + 8, HOTM_PANEL_W + PADDING_X * 2 + 80)));
        } else if (processedLines != null) {
            int maxLineW = measureMaxLineWidth(tr, processedLines, null, hasQuestion ? currentQuestion : null);
            contentW = Math.min(maxW, Math.max(MIN_WIDTH, maxLineW + PADDING_X * 2));
            int linesH = 0;
            for (OverlayLine l : processedLines) linesH += (l.type == LineType.SPACER) ? 6 : LINE_HEIGHT;
            bodyH = PADDING_Y + linesH + PADDING_Y;
        } else {
            return;
        }

        boolean showFeedback = !thinking && rawLines != null;
        int feedbackH = showFeedback ? FEEDBACK_BAR_H : 0;
        int totalH = HEADER_HEIGHT + 1 + questionBarH + bodyH + feedbackH;
        int x = screenW - contentW - MARGIN_RIGHT;
        int y = MARGIN_TOP;

        // ===== Pre-calculate key Y positions =====
        int accentY = y + HEADER_HEIGHT;
        int contentY = y + HEADER_HEIGHT + 1;
        int questionY = contentY;
        if (hasQuestion) contentY += questionBarH;
        int bodyStartY = contentY + PADDING_Y;
        int feedbackY = y + totalH - feedbackH;

        // HOTM panel position
        int hotmPanelX = x + contentW - PADDING_X - HOTM_PANEL_W;
        int hotmPanelY = bodyStartY;

        // ============================================================
        //  PHASE 1: NVG SHAPE PASS
        // ============================================================
        boolean nvg = NVGRenderer.isReady();
        if (nvg) {
            NVGRenderer.beginFrame();

            // --- Shadow ---
            NVGRenderer.dropShadow(x, y, contentW, totalH, R, 12, 0xFF000000, 0.4f * alpha);

            // --- Panel background ---
            NVGRenderer.roundedRect(x, y, contentW, totalH, R, 0xF01A1A2E, alpha);

            // --- Header (3 gradient bands + rounded top) ---
            int bandH = HEADER_HEIGHT / 3;
            NVGRenderer.roundedRectTop(x, y, contentW, bandH, R, 0xFF30304A, alpha);
            NVGRenderer.rect(x, y + bandH, contentW, bandH, 0xFF2C2C44, alpha);
            NVGRenderer.rect(x, y + bandH * 2, contentW, HEADER_HEIGHT - bandH * 2, 0xFF282840, alpha);

            // Top highlight
            NVGRenderer.rect(x + R, y, contentW - R * 2, 1, 0x448888CC, alpha);

            // Accent line
            NVGRenderer.horizontalGradient(x, accentY, contentW, 1, 0, 0xFF00BBEE, 0xFF6366F1, alpha);

            // --- Header dots ---
            float dotCY = y + HEADER_HEIGHT / 2f;
            float dotCX = x + 9;
            NVGRenderer.circle(dotCX, dotCY, 2.5f, 0xFF5F57, alpha);
            NVGRenderer.circle(dotCX + 8, dotCY, 2.5f, 0xFFBD2E, alpha);
            NVGRenderer.circle(dotCX + 16, dotCY, 2.5f, 0xFF28C840, alpha);

            // --- Question bar background ---
            if (hasQuestion) {
                NVGRenderer.rect(x, questionY, contentW, questionBarH, 0xFF1E1E30, alpha);
                NVGRenderer.rect(x + PADDING_X, questionY + questionBarH - 1,
                        contentW - PADDING_X * 2, 1, 0x33555577, alpha);
            }

            // --- HOTM grid shapes ---
            if (hasHotm && hotm != null && narrowLines != null) {
                drawHotmShapes(hotm, hotmPanelX, hotmPanelY, alpha);
            }

            // --- Feedback bar shapes ---
            if (showFeedback) {
                // Separator
                NVGRenderer.rect(x + PADDING_X, feedbackY, contentW - PADDING_X * 2, 1, 0x33555577, alpha);

                if (feedbackVote == null) {
                    // Button backgrounds
                    String yKey = "[Y]";
                    String correctLabel = " Correct";
                    String nKey = "[N]";
                    String wrongLabel = " Wrong";
                    int yKeyW = tr.getWidth(yKey);
                    int correctLabelW = tr.getWidth(correctLabel);
                    int nKeyW = tr.getWidth(nKey);
                    int wrongLabelW = tr.getWidth(wrongLabel);
                    int gap = 14;
                    int totalBtnW = yKeyW + correctLabelW + gap + nKeyW + wrongLabelW;
                    int btnX = x + (contentW - totalBtnW) / 2;

                    int correctFullW = yKeyW + correctLabelW + 6;
                    NVGRenderer.roundedRect(btnX - 3, feedbackY + 1, correctFullW, FEEDBACK_BAR_H - 2, 3, 0x55228822, alpha);
                    NVGRenderer.rect(btnX - 1, feedbackY + 2, yKeyW + 2, FEEDBACK_BAR_H - 4, 0x4433AA33, alpha);

                    int wrongX = btnX + yKeyW + correctLabelW + gap;
                    int wrongFullW = nKeyW + wrongLabelW + 6;
                    NVGRenderer.roundedRect(wrongX - 3, feedbackY + 1, wrongFullW, FEEDBACK_BAR_H - 2, 3, 0x55882222, alpha);
                    NVGRenderer.rect(wrongX - 1, feedbackY + 2, nKeyW + 2, FEEDBACK_BAR_H - 4, 0x44AA3333, alpha);
                }
            }

            // --- Bottom edge ---
            NVGRenderer.rect(x + R, y + totalH - 1, contentW - R * 2, 1, 0x22000000, alpha);

            NVGRenderer.endFrame();
        }

        // ============================================================
        //  PHASE 2: TEXT PASS (MC TextRenderer)
        // ============================================================

        // --- Title ---
        int titleX = x + 9 + 24 + 4;
        context.drawText(tr, "SkyAI", titleX, y + (HEADER_HEIGHT - 8) / 2,
                withAlpha(0xFF00DDFF, alpha), false);
        String ver = "v" + HypixelAIUpdater.MOD_VERSION;
        int verW = tr.getWidth(ver);
        context.drawText(tr, ver, x + contentW - verW - PADDING_X, y + (HEADER_HEIGHT - 8) / 2,
                withAlpha(0xFF555566, alpha), false);

        // --- Question text ---
        if (hasQuestion) {
            String qText = "> " + currentQuestion;
            if (tr.getWidth(qText) > contentW - PADDING_X * 2)
                qText = qText.substring(0, Math.min(qText.length(), 40)) + "...";
            context.drawText(tr, qText, x + PADDING_X, questionY + 3,
                    withAlpha(0xFF44AACC, alpha), false);
        }

        // --- Body ---
        int cy = bodyStartY;
        if (thinking) {
            long dots = ((now - thinkingStart) / 400) % 4;
            String thinkText = "Thinking" + ".".repeat((int) dots);
            context.drawText(tr, thinkText, x + PADDING_X, cy, withAlpha(0xFF888899, alpha), false);
        } else if (hasHotm && narrowLines != null) {
            // Narrow text (beside grid)
            int textX = x + PADDING_X;
            int textCy = cy;
            for (OverlayLine line : narrowLines) {
                if (line.type == LineType.SPACER) { textCy += 6; continue; }
                drawTextLine(context, tr, line, textX, textCy, alpha);
                textCy += LINE_HEIGHT;
            }
            // HOTM text (title + legend)
            drawHotmText(context, tr, hotmPanelX, hotmPanelY, alpha);
            // Full-width text (below grid)
            cy = hotmPanelY + HOTM_PANEL_H + 6;
            if (fullLines != null) {
                int ftx = x + PADDING_X;
                for (OverlayLine line : fullLines) {
                    if (line.type == LineType.SPACER) { cy += 6; continue; }
                    drawTextLine(context, tr, line, ftx, cy, alpha);
                    cy += LINE_HEIGHT;
                }
            }
        } else if (processedLines != null) {
            int tx = x + PADDING_X;
            for (OverlayLine line : processedLines) {
                if (line.type == LineType.SPACER) { cy += 6; continue; }
                drawTextLine(context, tr, line, tx, cy, alpha);
                cy += LINE_HEIGHT;
            }
        }

        // --- Feedback text ---
        if (showFeedback) {
            if (feedbackVote != null) {
                String msg = feedbackVote.equals("up") ? "\u2714 Thanks for the feedback!" : "\u2716 Noted \u2014 we'll improve!";
                int msgColor = feedbackVote.equals("up") ? COLOR_GREEN : COLOR_GOLD;
                int msgW = tr.getWidth(msg);
                context.drawText(tr, msg, x + (contentW - msgW) / 2, feedbackY + 3,
                        withAlpha(msgColor, alpha), false);
            } else {
                String yKey = "[Y]", correctLabel = " Correct", nKey = "[N]", wrongLabel = " Wrong";
                int yKeyW = tr.getWidth(yKey);
                int correctLabelW = tr.getWidth(correctLabel);
                int nKeyW = tr.getWidth(nKey);
                int wrongLabelW = tr.getWidth(wrongLabel);
                int gap = 14;
                int totalBtnW = yKeyW + correctLabelW + gap + nKeyW + wrongLabelW;
                int btnX = x + (contentW - totalBtnW) / 2;

                context.drawText(tr, yKey, btnX, feedbackY + 3, withAlpha(COLOR_GREEN, alpha), false);
                context.drawText(tr, correctLabel, btnX + yKeyW, feedbackY + 3, withAlpha(COLOR_GREEN, alpha), false);

                int wrongX = btnX + yKeyW + correctLabelW + gap;
                context.drawText(tr, nKey, wrongX, feedbackY + 3, withAlpha(COLOR_RED, alpha), false);
                context.drawText(tr, wrongLabel, wrongX + nKeyW, feedbackY + 3, withAlpha(COLOR_RED, alpha), false);
            }
        }

        // If NVG was NOT available, draw shapes as legacy fallback
        // (shapes are behind text, so this ordering still works visually with alpha)
        if (!nvg) {
            renderLegacyShapes(context, x, y, contentW, totalH, alpha, hasQuestion, questionY,
                    questionBarH, hasHotm, hotm, hotmPanelX, hotmPanelY, showFeedback, feedbackY, tr);
        }
    }

    // ===================== HOTM Shapes (NVG) =====================

    private static void drawHotmShapes(int[] grid, int px, int py, float alpha) {
        // Panel background
        NVGRenderer.roundedRect(px, py, HOTM_PANEL_W, HOTM_PANEL_H, 3, 0xFF12121E, alpha);
        // Border
        NVGRenderer.strokeRect(px, py, HOTM_PANEL_W, HOTM_PANEL_H, 3, 1, 0x55444466, alpha);

        int innerX = px + HOTM_PANEL_PAD;
        int gridY = py + HOTM_PANEL_PAD + HOTM_TITLE_H + 2;

        // Grid background
        NVGRenderer.rect(innerX - 1, gridY - 1, GRID_W + 2, GRID_H + 2, 0xFF0E0E16, alpha);

        // Grid cells
        for (int row = 0; row < GRID_ROWS; row++) {
            int tier = 9 - row;
            for (int c = 0; c < GRID_COLS; c++) {
                int state = grid[tier * 7 + c];
                if (state == 0) continue;
                float cx = innerX + CELL_GAP + c * (CELL_SIZE + CELL_GAP);
                float cy = gridY + CELL_GAP + row * (CELL_SIZE + CELL_GAP);
                int cellColor = switch (state) {
                    case -1 -> 0xFF333333;
                    case 1  -> 0xFF555555;
                    case 2  -> 0xFFFFAA00;
                    case 3  -> 0xFF55FF55;
                    case 4  -> 0xFF55FFFF;
                    case 5  -> 0xFFFF55FF;
                    default -> 0xFF444444;
                };
                NVGRenderer.rect(cx, cy, CELL_SIZE, CELL_SIZE, cellColor, alpha);
                // Inner highlight
                if (state > 0) {
                    NVGRenderer.rect(cx, cy, CELL_SIZE, 1, 0x33FFFFFF, alpha);
                    NVGRenderer.rect(cx, cy, 1, CELL_SIZE, 0x33FFFFFF, alpha);
                }
            }
        }

        // Legend color swatches
        int legendY = gridY + GRID_H + 4;
        int lx = innerX;
        NVGRenderer.rect(lx, legendY + 1, 4, 4, 0xFF55FF55, alpha);
        lx += 14;
        NVGRenderer.rect(lx, legendY + 1, 4, 4, 0xFFFFAA00, alpha);
        lx += 12;
        NVGRenderer.rect(lx, legendY + 1, 4, 4, 0xFF555555, alpha);
        lx += 10;
        NVGRenderer.rect(lx, legendY + 1, 4, 4, 0xFF333333, alpha);
    }

    // ===================== HOTM Text (MC) =====================

    private static void drawHotmText(DrawContext ctx, TextRenderer tr, int px, int py, float alpha) {
        int innerX = px + HOTM_PANEL_PAD;
        int innerY = py + HOTM_PANEL_PAD;

        // Title
        String title = "HotM Tree";
        int titleW = tr.getWidth(title);
        ctx.drawText(tr, title, innerX + (GRID_W - titleW) / 2, innerY,
                withAlpha(COLOR_GOLD, alpha), false);

        // Legend labels
        int legendY = innerY + HOTM_TITLE_H + 2 + GRID_H + 4;
        int lx = innerX + 5;
        ctx.drawText(tr, "M", lx, legendY, withAlpha(COLOR_GRAY, alpha), false);
        lx += tr.getWidth("M") + 4;
        ctx.drawText(tr, "L", lx + 5, legendY, withAlpha(COLOR_GRAY, alpha), false);
        lx += tr.getWidth("L") + 8;
        ctx.drawText(tr, "0", lx + 5, legendY, withAlpha(COLOR_GRAY, alpha), false);
        lx += tr.getWidth("0") + 8;
        ctx.drawText(tr, "\u2716", lx + 5, legendY, withAlpha(COLOR_GRAY, alpha), false);
    }

    // ===================== Legacy shape fallback =====================

    private static void renderLegacyShapes(DrawContext ctx, int x, int y, int contentW, int totalH,
                                           float alpha, boolean hasQuestion, int questionY, int questionBarH,
                                           boolean hasHotm, int[] hotm, int hotmPanelX, int hotmPanelY,
                                           boolean showFeedback, int feedbackY, TextRenderer tr) {
        // Shadow
        for (int i = 4; i >= 1; i--) {
            int sa = (int) (((5 - i) * 12) * alpha);
            if (sa > 0) fillRoundedLegacy(ctx, x - i + 1, y - i + 2, contentW + (i - 1) * 2,
                    totalH + (i - 1) * 2, R + i - 1, (sa << 24));
        }
        // Panel
        fillRoundedLegacy(ctx, x, y, contentW, totalH, R, col(0xF0, 0x1A, 0x1A, 0x2E, alpha));
        // Header
        int bandH = HEADER_HEIGHT / 3;
        fillRoundedTopLegacy(ctx, x, y, contentW, bandH, R, col(0xFF, 0x30, 0x30, 0x4A, alpha));
        fillLegacy(ctx, x, y + bandH, x + contentW, y + bandH * 2, col(0xFF, 0x2C, 0x2C, 0x44, alpha));
        fillLegacy(ctx, x, y + bandH * 2, x + contentW, y + HEADER_HEIGHT, col(0xFF, 0x28, 0x28, 0x40, alpha));
        fillLegacy(ctx, x + R, y, x + contentW - R, y + 1, col(0x44, 0x88, 0x88, 0xCC, alpha));
        fillLegacy(ctx, x, y + HEADER_HEIGHT, x + contentW, y + HEADER_HEIGHT + 1, col(0xFF, 0x00, 0xBB, 0xEE, alpha));
        // Dots
        int dotCY = y + HEADER_HEIGHT / 2;
        drawDotLegacy(ctx, x + 9, dotCY, 0xFF5F57, alpha);
        drawDotLegacy(ctx, x + 17, dotCY, 0xFFBD2E, alpha);
        drawDotLegacy(ctx, x + 25, dotCY, 0x28C840, alpha);
        // Question bar
        if (hasQuestion) {
            fillLegacy(ctx, x, questionY, x + contentW, questionY + questionBarH, col(0xFF, 0x1E, 0x1E, 0x30, alpha));
            fillLegacy(ctx, x + PADDING_X, questionY + questionBarH - 1,
                    x + contentW - PADDING_X, questionY + questionBarH, col(0x33, 0x55, 0x55, 0x77, alpha));
        }
        // Bottom edge
        fillLegacy(ctx, x + R, y + totalH - 1, x + contentW - R, y + totalH, col(0x22, 0x00, 0x00, 0x00, alpha));
    }

    // ===================== Text line rendering =====================

    private static void drawTextLine(DrawContext ctx, TextRenderer tr, OverlayLine line, int tx, int cy, float alpha) {
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
                String stripped = line.text.replaceAll("\u00a7.", "");
                int dotIdx = stripped.indexOf('.');
                if (dotIdx > 0 && dotIdx < 4) {
                    String num = stripped.substring(0, dotIdx + 1);
                    ctx.drawText(tr, num, lx, cy, withAlpha(COLOR_AQUA, alpha), false);
                    int numW = tr.getWidth(num + " ");
                    String rest = line.text;
                    int realDot = rest.replaceAll("\u00a7.", "").indexOf('.');
                    if (realDot >= 0) {
                        int pos = 0, spos = 0;
                        while (pos < rest.length() && spos <= realDot) {
                            if (rest.charAt(pos) == '\u00a7' && pos + 1 < rest.length()) pos += 2;
                            else { spos++; pos++; }
                        }
                        while (pos < rest.length() && rest.charAt(pos) == ' ') pos++;
                        drawColoredText(ctx, tr, parseColorSegments(rest.substring(pos)), lx + numW, cy, alpha);
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

    // ===================== Line processing (unchanged) =====================

    private static void processLinesWithHotm(TextRenderer tr, String[] lines, int panelW) {
        int fullWrap = panelW - PADDING_X * 2;
        int narrowWrap = panelW - PADDING_X * 2 - HOTM_PANEL_W - 8;
        int hotmPanelLines = HOTM_PANEL_H / LINE_HEIGHT + 1;

        List<OverlayLine> allWrapped = new ArrayList<>();
        for (String line : lines) {
            if (line.isEmpty()) { allWrapped.add(new OverlayLine("", LineType.SPACER, 0, null)); continue; }
            LineType type = LineType.NORMAL;
            String content = line;
            int indent = 0;
            if (line.startsWith("- ") || line.startsWith("* ")) { type = LineType.BULLET; content = line.substring(2); indent = 8; }
            else if (line.matches("^\\d+\\.\\s.*")) { type = LineType.NUMBERED; indent = 4; }
            wrapLine(tr, content, type, indent, narrowWrap, allWrapped);
        }

        List<OverlayLine> narrow = new ArrayList<>();
        List<OverlayLine> full = new ArrayList<>();
        for (int i = 0; i < allWrapped.size(); i++) {
            if (i < hotmPanelLines) narrow.add(allWrapped.get(i));
            else full.add(allWrapped.get(i));
        }
        narrowLines = narrow;
        fullLines = full;
    }

    private static void processLinesNormal(TextRenderer tr, String[] lines, int panelW) {
        int wrapWidth = panelW - PADDING_X * 2;
        List<OverlayLine> result = new ArrayList<>();
        for (String line : lines) {
            if (line.isEmpty()) { result.add(new OverlayLine("", LineType.SPACER, 0, null)); continue; }
            LineType type = LineType.NORMAL;
            String content = line;
            int indent = 0;
            if (line.startsWith("- ") || line.startsWith("* ")) { type = LineType.BULLET; content = line.substring(2); indent = 8; }
            else if (line.matches("^\\d+\\.\\s.*")) { type = LineType.NUMBERED; indent = 4; }
            wrapLine(tr, content, type, indent, wrapWidth, result);
        }
        processedLines = result;
    }

    private static void wrapLine(TextRenderer tr, String content, LineType type, int indent,
                                 int wrapWidth, List<OverlayLine> out) {
        String stripped = content.replaceAll("\u00a7.", "");
        int availWidth = wrapWidth - indent;
        if (tr.getWidth(stripped) <= availWidth) {
            out.add(new OverlayLine(content, type, indent, parseColorSegments(content)));
        } else {
            String[] words = content.split(" ");
            StringBuilder current = new StringBuilder();
            boolean first = true;
            for (String word : words) {
                String testStripped = (current + (current.length() > 0 ? " " : "") + word).replaceAll("\u00a7.", "");
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
            if (c == '\u00a7' && i + 1 < text.length()) {
                if (current.length() > 0) {
                    segments.add(new ColorSegment(current.toString(), currentColor));
                    current = new StringBuilder();
                }
                char code = text.charAt(i + 1);
                int newColor = colorForCode(code);
                if (newColor != -1) currentColor = newColor;
                else if (code == 'r') currentColor = COLOR_BODY;
                i++;
            } else {
                current.append(c);
            }
        }
        if (current.length() > 0) segments.add(new ColorSegment(current.toString(), currentColor));
        return segments;
    }

    private static int colorForCode(char code) {
        return switch (code) {
            case '0' -> COLOR_BLACK;  case '1' -> COLOR_DARK_BLUE; case '2' -> COLOR_DARK_GREEN;
            case '3' -> COLOR_DARK_AQUA; case '4' -> COLOR_DARK_RED; case '5' -> COLOR_DARK_PURPLE;
            case '6' -> COLOR_GOLD;   case '7' -> COLOR_GRAY;      case '8' -> COLOR_DARK_GRAY;
            case '9' -> COLOR_BLUE;   case 'a' -> COLOR_GREEN;     case 'b' -> COLOR_AQUA;
            case 'c' -> COLOR_RED;    case 'd' -> COLOR_LIGHT_PURPLE; case 'e' -> COLOR_YELLOW;
            case 'f' -> COLOR_WHITE;  default -> -1;
        };
    }

    // ===================== Utility =====================

    private static int measureMaxLineWidth(TextRenderer tr, List<OverlayLine> lines1,
                                           List<OverlayLine> lines2, String question) {
        int max = 0;
        if (lines1 != null) for (OverlayLine l : lines1) {
            if (l.type != LineType.SPACER) {
                int w = tr.getWidth(l.text.replaceAll("\u00a7.", "")) + l.indent + 10;
                if (w > max) max = w;
            }
        }
        if (lines2 != null) for (OverlayLine l : lines2) {
            if (l.type != LineType.SPACER) {
                int w = tr.getWidth(l.text.replaceAll("\u00a7.", "")) + l.indent + 10;
                if (w > max) max = w;
            }
        }
        if (question != null) {
            int qw = tr.getWidth("> " + question) + 10;
            if (qw > max) max = qw;
        }
        return max;
    }

    private static int withAlpha(int argb, float alpha) {
        int a = (int) (((argb >> 24) & 0xFF) * alpha);
        return (a << 24) | (argb & 0x00FFFFFF);
    }

    private static int col(int a, int r, int g, int b, float alpha) {
        return ((int) (a * alpha) << 24) | (r << 16) | (g << 8) | b;
    }

    // ===================== Legacy drawing helpers =====================

    private static void drawDotLegacy(DrawContext ctx, int cx, int cy, int rgb, float alpha) {
        int c = col(0xFF, (rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF, alpha);
        fillLegacy(ctx, cx - 1, cy - 2, cx + 2, cy + 3, c);
        fillLegacy(ctx, cx - 2, cy - 1, cx + 3, cy + 2, c);
    }

    private static void fillRoundedLegacy(DrawContext ctx, int x, int y, int w, int h, int r, int color) {
        if (h <= 0 || w <= 0) return;
        int[] insets = r >= 3 ? new int[]{3, 1, 1} : r >= 2 ? new int[]{2, 1} : new int[]{1};
        for (int i = 0; i < insets.length && i < h; i++)
            fillLegacy(ctx, x + insets[i], y + i, x + w - insets[i], y + i + 1, color);
        int midStart = Math.min(insets.length, h);
        int midEnd = Math.max(midStart, h - insets.length);
        if (midEnd > midStart) fillLegacy(ctx, x, y + midStart, x + w, y + midEnd, color);
        for (int i = 0; i < insets.length && (h - 1 - i) >= midEnd; i++)
            fillLegacy(ctx, x + insets[i], y + h - 1 - i, x + w - insets[i], y + h - i, color);
    }

    private static void fillRoundedTopLegacy(DrawContext ctx, int x, int y, int w, int h, int r, int color) {
        if (h <= 0 || w <= 0) return;
        int[] insets = r >= 3 ? new int[]{3, 1, 1} : r >= 2 ? new int[]{2, 1} : new int[]{1};
        for (int i = 0; i < insets.length && i < h; i++)
            fillLegacy(ctx, x + insets[i], y + i, x + w - insets[i], y + i + 1, color);
        int midStart = Math.min(insets.length, h);
        if (h > midStart) fillLegacy(ctx, x, y + midStart, x + w, y + h, color);
    }

    private static void fillLegacy(DrawContext ctx, int x1, int y1, int x2, int y2, int argb) {
        if (((argb >> 24) & 0xFF) <= 0) return;
        ctx.fill(x1, y1, x2, y2, argb);
    }

    // ===================== Data classes =====================

    private enum LineType { NORMAL, BULLET, BULLET_CONT, NUMBERED, SPACER }

    private static class ColorSegment {
        final String text;
        final int color;
        ColorSegment(String t, int c) { text = t; color = c; }
    }

    private static class OverlayLine {
        final String text;
        final LineType type;
        final int indent;
        final List<ColorSegment> segments;
        OverlayLine(String t, LineType type, int indent, List<ColorSegment> segs) {
            this.text = t; this.type = type; this.indent = indent; this.segments = segs;
        }
    }
}
