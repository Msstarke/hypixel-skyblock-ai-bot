package com.hypixelai;

import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.client.input.KeyInput;
import net.minecraft.text.OrderedText;
import net.minecraft.text.Text;
import org.lwjgl.glfw.GLFW;

import java.util.ArrayList;
import java.util.List;

/**
 * macOS terminal-style overlay for displaying AI responses.
 */
public class SkyAIScreen extends Screen {

    // Colors (ARGB)
    private static final int BG_COLOR       = 0xF0181820; // dark bg, slightly transparent
    private static final int TITLEBAR_COLOR = 0xFF222230; // title bar
    private static final int BORDER_COLOR   = 0xFF2A2A3A; // subtle border
    private static final int ACCENT_COLOR   = 0xFF00C8FF; // cyan accent
    private static final int TEXT_COLOR     = 0xFFCCCCCC; // body text
    private static final int QUESTION_COLOR = 0xFFFFFFFF; // white for question
    private static final int MUTED_COLOR   = 0xFF666666; // muted gray
    private static final int BULLET_COLOR  = 0xFFFFAA00; // gold bullets
    private static final int NUM_COLOR     = 0xFF00C8FF; // cyan numbers
    private static final int SCROLLBAR_BG  = 0xFF2A2A3A;
    private static final int SCROLLBAR_FG  = 0xFF555566;

    // macOS dots
    private static final int DOT_RED    = 0xFFFF5F57;
    private static final int DOT_YELLOW = 0xFFFFBD2E;
    private static final int DOT_GREEN  = 0xFF28C840;

    // Layout
    private static final int WINDOW_PADDING = 12;
    private static final int TITLEBAR_HEIGHT = 28;
    private static final int LINE_SPACING = 12;
    private static final int DOT_SIZE = 10;
    private static final int DOT_GAP = 7;
    private static final int SCROLLBAR_WIDTH = 4;
    private static final int CORNER_INSET = 2;

    private final String question;
    private final String[] responseLines;
    private List<ResponseLine> wrappedLines;

    private int windowX, windowY, windowW, windowH;
    private int contentHeight;
    private int visibleHeight;
    private float scrollOffset = 0;
    private float targetScroll = 0;
    private boolean isDraggingScrollbar = false;

    // Fade-in animation
    private long openTime;
    private static final long FADE_MS = 150;

    public SkyAIScreen(String question, String[] responseLines) {
        super(Text.literal("SkyAI"));
        this.question = question;
        this.responseLines = responseLines;
        this.openTime = System.currentTimeMillis();
    }

    @Override
    protected void init() {
        super.init();

        // Window size: 60% of screen width, up to 70% of screen height
        windowW = Math.min((int)(width * 0.6), 500);
        windowW = Math.max(windowW, 300);
        windowH = Math.min((int)(height * 0.7), 500);
        windowH = Math.max(windowH, 200);

        // Center
        windowX = (width - windowW) / 2;
        windowY = (height - windowH) / 2;

        // Wrap text
        wrapLines();
    }

    private void wrapLines() {
        wrappedLines = new ArrayList<>();
        int maxWidth = windowW - WINDOW_PADDING * 2 - SCROLLBAR_WIDTH - 8;

        // Add question as first line (special styling)
        wrappedLines.add(new ResponseLine(question, LineType.QUESTION));
        wrappedLines.add(new ResponseLine("", LineType.SPACER));

        for (String line : responseLines) {
            if (line.isEmpty()) {
                wrappedLines.add(new ResponseLine("", LineType.SPACER));
                continue;
            }

            LineType type = LineType.NORMAL;
            String content = line;

            if (line.startsWith("- ") || line.startsWith("* ")) {
                type = LineType.BULLET;
                content = line.substring(2);
            } else if (line.matches("^\\d+\\.\\s.*")) {
                type = LineType.NUMBERED;
            }

            // Word wrap
            List<String> wrapped = wordWrap(content, maxWidth - (type == LineType.BULLET ? 12 : 0));
            for (int i = 0; i < wrapped.size(); i++) {
                if (i == 0) {
                    wrappedLines.add(new ResponseLine(wrapped.get(i), type));
                } else {
                    // Continuation lines for wrapped text
                    wrappedLines.add(new ResponseLine(wrapped.get(i),
                            type == LineType.BULLET ? LineType.BULLET_CONT : LineType.NORMAL));
                }
            }
        }

        contentHeight = wrappedLines.size() * LINE_SPACING + WINDOW_PADDING;
        visibleHeight = windowH - TITLEBAR_HEIGHT - WINDOW_PADDING * 2;
    }

    private List<String> wordWrap(String text, int maxWidth) {
        List<String> lines = new ArrayList<>();
        TextRenderer tr = textRenderer;

        if (tr.getWidth(text) <= maxWidth) {
            lines.add(text);
            return lines;
        }

        String[] words = text.split(" ");
        StringBuilder current = new StringBuilder();

        for (String word : words) {
            String test = current.length() == 0 ? word : current + " " + word;
            if (tr.getWidth(test) > maxWidth && current.length() > 0) {
                lines.add(current.toString());
                current = new StringBuilder(word);
            } else {
                if (current.length() > 0) current.append(" ");
                current.append(word);
            }
        }
        if (current.length() > 0) lines.add(current.toString());

        return lines;
    }

    @Override
    public void render(DrawContext context, int mouseX, int mouseY, float delta) {
        // Fade-in alpha
        long elapsed = System.currentTimeMillis() - openTime;
        float alpha = Math.min(1f, (float)elapsed / FADE_MS);

        // Smooth scroll
        scrollOffset += (targetScroll - scrollOffset) * 0.3f;

        // Darken background
        context.fill(0, 0, width, height, (int)(alpha * 0x80) << 24);

        // Window shadow
        int shadowAlpha = (int)(alpha * 0x40);
        context.fill(windowX + 3, windowY + 3, windowX + windowW + 3, windowY + windowH + 3,
                (shadowAlpha << 24));

        // Window background
        context.fill(windowX, windowY, windowX + windowW, windowY + windowH, applyAlpha(BG_COLOR, alpha));

        // Border
        drawBorder(context, windowX, windowY, windowW, windowH, applyAlpha(BORDER_COLOR, alpha));

        // Title bar
        context.fill(windowX, windowY, windowX + windowW, windowY + TITLEBAR_HEIGHT,
                applyAlpha(TITLEBAR_COLOR, alpha));

        // Bottom edge of title bar
        context.fill(windowX, windowY + TITLEBAR_HEIGHT - 1, windowX + windowW,
                windowY + TITLEBAR_HEIGHT, applyAlpha(BORDER_COLOR, alpha));

        // macOS dots
        int dotY = windowY + TITLEBAR_HEIGHT / 2;
        int dotX = windowX + 14;
        drawDot(context, dotX, dotY, DOT_RED, alpha);
        drawDot(context, dotX + DOT_SIZE + DOT_GAP, dotY, DOT_YELLOW, alpha);
        drawDot(context, dotX + (DOT_SIZE + DOT_GAP) * 2, dotY, DOT_GREEN, alpha);

        // Title text
        String titleText = "\u2B25 SkyAI";
        int titleWidth = textRenderer.getWidth(titleText);
        context.drawTextWithShadow(textRenderer, titleText,
                windowX + windowW / 2 - titleWidth / 2, windowY + TITLEBAR_HEIGHT / 2 - 4,
                applyAlpha(ACCENT_COLOR, alpha));

        // Version in title bar (right side)
        String version = "v" + HypixelAIUpdater.MOD_VERSION;
        int versionWidth = textRenderer.getWidth(version);
        context.drawText(textRenderer, version,
                windowX + windowW - versionWidth - 10, windowY + TITLEBAR_HEIGHT / 2 - 4,
                applyAlpha(MUTED_COLOR, alpha), false);

        // Content area with scissor (clipping)
        int contentY = windowY + TITLEBAR_HEIGHT + WINDOW_PADDING;
        int contentX = windowX + WINDOW_PADDING;
        int contentW = windowW - WINDOW_PADDING * 2 - SCROLLBAR_WIDTH - 4;

        context.enableScissor(windowX + 1, windowY + TITLEBAR_HEIGHT,
                windowX + windowW - 1, windowY + windowH - 1);

        // Render lines
        int y = contentY - (int)scrollOffset;
        for (ResponseLine line : wrappedLines) {
            if (y + LINE_SPACING > windowY + TITLEBAR_HEIGHT && y < windowY + windowH) {
                renderLine(context, line, contentX, y, contentW, alpha);
            }
            y += LINE_SPACING;
        }

        context.disableScissor();

        // Scrollbar
        if (contentHeight > visibleHeight) {
            renderScrollbar(context, alpha, mouseX, mouseY);
        }

        // Close hint at bottom
        String hint = "ESC to close  |  Scroll for more";
        int hintWidth = textRenderer.getWidth(hint);
        context.drawText(textRenderer, hint,
                windowX + windowW / 2 - hintWidth / 2,
                windowY + windowH + 6,
                applyAlpha(MUTED_COLOR, alpha), false);
    }

    private void renderLine(DrawContext context, ResponseLine line, int x, int y, int maxW, float alpha) {
        switch (line.type) {
            case QUESTION:
                // Question with accent bar
                context.fill(x - 4, y - 1, x - 1, y + 9, applyAlpha(ACCENT_COLOR, alpha));
                context.drawTextWithShadow(textRenderer, line.text, x + 4, y,
                        applyAlpha(QUESTION_COLOR, alpha));
                break;

            case BULLET:
                context.drawTextWithShadow(textRenderer, "\u2022", x + 2, y,
                        applyAlpha(BULLET_COLOR, alpha));
                context.drawText(textRenderer, line.text, x + 14, y,
                        applyAlpha(TEXT_COLOR, alpha), false);
                break;

            case BULLET_CONT:
                context.drawText(textRenderer, line.text, x + 14, y,
                        applyAlpha(TEXT_COLOR, alpha), false);
                break;

            case NUMBERED:
                // Color the number part
                int dotIdx = line.text.indexOf('.');
                if (dotIdx > 0 && dotIdx < 4) {
                    String num = line.text.substring(0, dotIdx + 1);
                    String rest = line.text.substring(dotIdx + 1).trim();
                    context.drawTextWithShadow(textRenderer, num, x + 2, y,
                            applyAlpha(NUM_COLOR, alpha));
                    int numW = textRenderer.getWidth(num + " ");
                    context.drawText(textRenderer, rest, x + 2 + numW, y,
                            applyAlpha(TEXT_COLOR, alpha), false);
                } else {
                    context.drawText(textRenderer, line.text, x + 2, y,
                            applyAlpha(TEXT_COLOR, alpha), false);
                }
                break;

            case SPACER:
                break;

            default:
                context.drawText(textRenderer, line.text, x + 2, y,
                        applyAlpha(TEXT_COLOR, alpha), false);
                break;
        }
    }

    private void renderScrollbar(DrawContext context, float alpha, int mouseX, int mouseY) {
        int sbX = windowX + windowW - SCROLLBAR_WIDTH - 4;
        int sbTop = windowY + TITLEBAR_HEIGHT + 4;
        int sbBottom = windowY + windowH - 4;
        int sbHeight = sbBottom - sbTop;

        // Scrollbar track
        context.fill(sbX, sbTop, sbX + SCROLLBAR_WIDTH, sbBottom,
                applyAlpha(SCROLLBAR_BG, alpha));

        // Scrollbar thumb
        float scrollRange = Math.max(1, contentHeight - visibleHeight);
        float thumbRatio = (float)visibleHeight / contentHeight;
        int thumbHeight = Math.max(20, (int)(sbHeight * thumbRatio));
        int thumbY = sbTop + (int)((sbHeight - thumbHeight) * (scrollOffset / scrollRange));

        boolean hovered = mouseX >= sbX && mouseX <= sbX + SCROLLBAR_WIDTH
                && mouseY >= thumbY && mouseY <= thumbY + thumbHeight;

        context.fill(sbX, thumbY, sbX + SCROLLBAR_WIDTH, thumbY + thumbHeight,
                applyAlpha(hovered || isDraggingScrollbar ? ACCENT_COLOR : SCROLLBAR_FG, alpha));
    }

    private void drawBorder(DrawContext context, int x, int y, int w, int h, int color) {
        context.fill(x, y, x + w, y + 1, color);         // top
        context.fill(x, y + h - 1, x + w, y + h, color); // bottom
        context.fill(x, y, x + 1, y + h, color);          // left
        context.fill(x + w - 1, y, x + w, y + h, color);  // right
    }

    private void drawDot(DrawContext context, int cx, int cy, int color, float alpha) {
        int r = DOT_SIZE / 2;
        int col = applyAlpha(color, alpha);
        // Approximate circle with filled rects
        context.fill(cx - r + 1, cy - r, cx + r - 1, cy + r, col);
        context.fill(cx - r, cy - r + 1, cx + r, cy + r - 1, col);
    }

    private int applyAlpha(int argb, float alpha) {
        int a = (argb >> 24) & 0xFF;
        a = (int)(a * alpha);
        return (a << 24) | (argb & 0x00FFFFFF);
    }

    // --- Input handling ---

    @Override
    public boolean mouseScrolled(double mouseX, double mouseY, double horizontalAmount, double verticalAmount) {
        float scrollAmount = (float)(-verticalAmount * LINE_SPACING * 3);
        targetScroll = Math.max(0, Math.min(contentHeight - visibleHeight, targetScroll + scrollAmount));
        return true;
    }

    @Override
    public boolean keyPressed(KeyInput keyInput) {
        if (keyInput.key() == GLFW.GLFW_KEY_ESCAPE) {
            close();
            return true;
        }
        // Page up/down
        if (keyInput.key() == GLFW.GLFW_KEY_PAGE_UP) {
            targetScroll = Math.max(0, targetScroll - visibleHeight);
            return true;
        }
        if (keyInput.key() == GLFW.GLFW_KEY_PAGE_DOWN) {
            targetScroll = Math.min(contentHeight - visibleHeight, targetScroll + visibleHeight);
            return true;
        }
        // Arrow keys
        if (keyInput.key() == GLFW.GLFW_KEY_UP) {
            targetScroll = Math.max(0, targetScroll - LINE_SPACING * 2);
            return true;
        }
        if (keyInput.key() == GLFW.GLFW_KEY_DOWN) {
            targetScroll = Math.min(contentHeight - visibleHeight, targetScroll + LINE_SPACING * 2);
            return true;
        }
        return super.keyPressed(keyInput);
    }

    @Override
    public boolean shouldPause() {
        return false; // Don't pause the game
    }

    // --- Data types ---

    private enum LineType {
        QUESTION, NORMAL, BULLET, BULLET_CONT, NUMBERED, SPACER
    }

    private static class ResponseLine {
        final String text;
        final LineType type;

        ResponseLine(String text, LineType type) {
            this.text = text;
            this.type = type;
        }
    }
}
