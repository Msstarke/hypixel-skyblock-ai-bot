package com.hypixelai;

import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.Click;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.text.Text;

/**
 * In-game config screen for SkyAI.
 * Opens with !aiconfig or keybind.
 * Dark themed, toggle switches, categories.
 */
public class SkyAIConfigScreen extends Screen {

    // Colors matching the site theme
    private static final int BG = 0xFF060611;
    private static final int CARD_BG = 0xFF0a0a1a;
    private static final int CARD_BORDER = 0xFF16162a;
    private static final int ACCENT = 0xFF6366f1;
    private static final int ACCENT2 = 0xFFa855f7;
    private static final int TEXT_PRIMARY = 0xFFe2e8f0;
    private static final int TEXT_SECONDARY = 0xFF8892a8;
    private static final int TEXT_DIM = 0xFF4a5268;
    private static final int GREEN = 0xFF22c55e;
    private static final int RED = 0xFFef4444;
    private static final int TOGGLE_BG_ON = 0xFF22c55e;
    private static final int TOGGLE_BG_OFF = 0xFF2a2a3a;
    private static final int TOGGLE_KNOB = 0xFFe2e8f0;

    private static final int PANEL_W = 220;
    private static final int TOGGLE_W = 24;
    private static final int TOGGLE_H = 12;
    private static final int ROW_H = 28;

    // Settings data
    private static final String[][] SETTINGS = {
        {"cortisol", "Cortisol Gauge", "Stress meter replacing hearts"},
        {"hearts", "Hide Hearts", "Remove vanilla heart bar"},
        {"armor", "Hide Armor", "Remove armor bar"},
        {"actionbar", "Hide Action Bar", "Remove SkyBlock stat overlay"},
        {"overlay", "AI Overlay", "Show AI response HUD"},
        {"autoupdate", "Auto Update", "Check for updates while playing"},
    };

    private int panelX, panelY;

    public SkyAIConfigScreen() {
        super(Text.literal("SkyAI Settings"));
    }

    public static void open() {
        MinecraftClient.getInstance().setScreen(new SkyAIConfigScreen());
    }

    @Override
    protected void init() {
        panelX = (width - PANEL_W) / 2;
        panelY = (height - (SETTINGS.length * ROW_H + 80)) / 2;
    }

    @Override
    public void render(DrawContext ctx, int mouseX, int mouseY, float delta) {
        // Dim background
        ctx.fill(0, 0, width, height, 0xCC000000);

        int py = panelY;

        // Header
        ctx.fill(panelX - 1, py - 1, panelX + PANEL_W + 1, py + SETTINGS.length * ROW_H + 76, CARD_BORDER);
        ctx.fill(panelX, py, panelX + PANEL_W, py + SETTINGS.length * ROW_H + 75, CARD_BG);

        // Title bar with gradient accent line
        for (int i = 0; i < PANEL_W; i++) {
            float t = (float) i / PANEL_W;
            int r = (int) (0x63 + (0xa8 - 0x63) * t);
            int g = (int) (0x66 + (0x55 - 0x66) * t);
            int b = (int) (0xf1 + (0xf7 - 0xf1) * t);
            int color = 0xFF000000 | (r << 16) | (g << 8) | b;
            ctx.fill(panelX + i, py, panelX + i + 1, py + 2, color);
        }

        py += 12;

        // Title
        String title = "SkyAI Settings";
        int titleW = textRenderer.getWidth(title);
        ctx.drawText(textRenderer, title, panelX + (PANEL_W - titleW) / 2, py, TEXT_PRIMARY, false);
        py += 16;

        // Version
        String ver = "v" + HypixelAIUpdater.MOD_VERSION;
        int verW = textRenderer.getWidth(ver);
        ctx.drawText(textRenderer, ver, panelX + (PANEL_W - verW) / 2, py, TEXT_DIM, false);
        py += 18;

        // Separator
        ctx.fill(panelX + 12, py, panelX + PANEL_W - 12, py + 1, CARD_BORDER);
        py += 8;

        // Settings rows
        for (int i = 0; i < SETTINGS.length; i++) {
            String key = SETTINGS[i][0];
            String label = SETTINGS[i][1];
            String desc = SETTINGS[i][2];

            boolean on = getSettingValue(key);
            int rowY = py + i * ROW_H;

            // Hover highlight
            boolean hovered = mouseX >= panelX && mouseX <= panelX + PANEL_W
                    && mouseY >= rowY && mouseY <= rowY + ROW_H;
            if (hovered) {
                ctx.fill(panelX + 4, rowY, panelX + PANEL_W - 4, rowY + ROW_H, 0x10FFFFFF);
            }

            // Label
            ctx.drawText(textRenderer, label, panelX + 14, rowY + 4, TEXT_PRIMARY, false);

            // Description
            ctx.drawText(textRenderer, desc, panelX + 14, rowY + 15, TEXT_DIM, false);

            // Toggle switch
            int toggleX = panelX + PANEL_W - TOGGLE_W - 14;
            int toggleY = rowY + (ROW_H - TOGGLE_H) / 2;
            drawToggle(ctx, toggleX, toggleY, on);
        }

        // Footer
        int footerY = py + SETTINGS.length * ROW_H + 6;
        String footer = "Click to toggle \u2022 ESC to close";
        int footerW = textRenderer.getWidth(footer);
        ctx.drawText(textRenderer, footer, panelX + (PANEL_W - footerW) / 2, footerY, TEXT_DIM, false);
    }

    private void drawToggle(DrawContext ctx, int x, int y, boolean on) {
        // Background pill
        int bgColor = on ? TOGGLE_BG_ON : TOGGLE_BG_OFF;
        ctx.fill(x, y, x + TOGGLE_W, y + TOGGLE_H, bgColor);

        // Rounded corners (fake with small fills)
        ctx.fill(x + 1, y - 1, x + TOGGLE_W - 1, y, bgColor);
        ctx.fill(x + 1, y + TOGGLE_H, x + TOGGLE_W - 1, y + TOGGLE_H + 1, bgColor);
        ctx.fill(x - 1, y + 1, x, y + TOGGLE_H - 1, bgColor);
        ctx.fill(x + TOGGLE_W, y + 1, x + TOGGLE_W + 1, y + TOGGLE_H - 1, bgColor);

        // Knob
        int knobSize = TOGGLE_H - 4;
        int knobX = on ? x + TOGGLE_W - knobSize - 2 : x + 2;
        int knobY = y + 2;
        ctx.fill(knobX, knobY, knobX + knobSize, knobY + knobSize, TOGGLE_KNOB);
    }

    @Override
    public boolean mouseClicked(Click click, boolean bl) {
        if (click.button() == 0) {
            double mouseX = click.x();
            double mouseY = click.y();
            int py = panelY + 12 + 16 + 18 + 8;

            for (int i = 0; i < SETTINGS.length; i++) {
                int rowY = py + i * ROW_H;
                if (mouseX >= panelX && mouseX <= panelX + PANEL_W
                        && mouseY >= rowY && mouseY <= rowY + ROW_H) {
                    HypixelAIConfig.toggle(SETTINGS[i][0]);
                    return true;
                }
            }
        }

        return super.mouseClicked(click, bl);
    }

    @Override
    public boolean shouldPause() {
        return false;
    }

    private boolean getSettingValue(String key) {
        return switch (key) {
            case "cortisol" -> HypixelAIConfig.isCortisolBar();
            case "hearts" -> HypixelAIConfig.isHideHearts();
            case "armor" -> HypixelAIConfig.isHideArmor();
            case "actionbar" -> HypixelAIConfig.isHideActionBar();
            case "overlay" -> HypixelAIConfig.isOverlay();
            case "autoupdate" -> HypixelAIConfig.isAutoUpdate();
            default -> false;
        };
    }
}
