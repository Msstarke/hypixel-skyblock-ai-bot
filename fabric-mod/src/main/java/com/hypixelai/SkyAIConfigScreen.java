package com.hypixelai;

import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.Click;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.text.Text;

/**
 * In-game config screen for SkyAI.
 * Opens with !aiconfig or keybind.
 * NanoVG rendered — smooth rounded rects, gradients, drop shadow, animated toggles.
 */
public class SkyAIConfigScreen extends Screen {

    // Colors matching the site theme
    private static final int BG = 0xCC000000;
    private static final int CARD_BG = 0xFF0a0a1a;
    private static final int CARD_BORDER = 0xFF16162a;
    private static final int ACCENT = 0xFF6366f1;
    private static final int ACCENT2 = 0xFFa855f7;
    private static final int TEXT_PRIMARY = 0xFFe2e8f0;
    private static final int TEXT_DIM = 0xFF4a5268;
    private static final int GREEN = 0xFF22c55e;
    private static final int RED = 0xFFef4444;
    private static final int TOGGLE_ON = 0xFF22c55e;
    private static final int TOGGLE_OFF = 0xFF2a2a3a;
    private static final int TOGGLE_KNOB = 0xFFe2e8f0;
    private static final int HOVER_BG = 0x15FFFFFF;

    private static final float PANEL_W = 260;
    private static final float TOGGLE_W = 28;
    private static final float TOGGLE_H = 14;
    private static final float ROW_H = 32;
    private static final float CORNER_R = 8;

    private static final String[][] SETTINGS = {
        {"cortisol", "Cortisol Gauge", "Stress meter replacing hearts"},
        {"hearts", "Hide Hearts", "Remove vanilla heart bar"},
        {"armor", "Hide Armor", "Remove armor bar"},
        {"actionbar", "Hide Action Bar", "Remove SkyBlock stat overlay"},
        {"overlay", "AI Overlay", "Show AI response HUD"},
        {"autoupdate", "Auto Update", "Check for updates while playing"},
    };

    // Smooth toggle animation per setting (0 = off, 1 = on)
    private final float[] toggleAnim = new float[SETTINGS.length];

    private float panelX, panelY, totalH;

    public SkyAIConfigScreen() {
        super(Text.literal("SkyAI Settings"));
    }

    public static void open() {
        MinecraftClient.getInstance().setScreen(new SkyAIConfigScreen());
    }

    @Override
    protected void init() {
        totalH = SETTINGS.length * ROW_H + 100;
        panelX = (width - PANEL_W) / 2;
        panelY = (height - totalH) / 2;
        for (int i = 0; i < SETTINGS.length; i++) {
            toggleAnim[i] = getSettingValue(SETTINGS[i][0]) ? 1f : 0f;
        }
    }

    @Override
    public void render(DrawContext ctx, int mouseX, int mouseY, float delta) {
        // Animate toggles smoothly
        for (int i = 0; i < SETTINGS.length; i++) {
            float target = getSettingValue(SETTINGS[i][0]) ? 1f : 0f;
            toggleAnim[i] += (target - toggleAnim[i]) * 0.15f;
        }

        float py = panelY;
        float rowsStartY = py + 68; // after title + version + separator

        if (NVGRenderer.isReady()) {
            // ========== NVG SHAPE PASS ==========
            NVGRenderer.beginFrame();

            // Dim background
            NVGRenderer.rect(0, 0, width, height, BG, 1f);

            // Panel drop shadow
            NVGRenderer.dropShadow(panelX, panelY, PANEL_W, totalH, CORNER_R, 20, 0xFF000000, 0.5f);

            // Panel background
            NVGRenderer.roundedRect(panelX, panelY, PANEL_W, totalH, CORNER_R, CARD_BG, 1f);

            // Panel border (subtle)
            NVGRenderer.strokeRect(panelX, panelY, PANEL_W, totalH, CORNER_R, 1f, CARD_BORDER, 1f);

            // Gradient accent line at top
            NVGRenderer.horizontalGradient(panelX, panelY, PANEL_W, 2, CORNER_R, ACCENT, ACCENT2, 1f);

            // Separator line
            NVGRenderer.rect(panelX + 16, py + 58, PANEL_W - 32, 1, CARD_BORDER, 1f);

            // Setting rows
            for (int i = 0; i < SETTINGS.length; i++) {
                float rowY = rowsStartY + i * ROW_H;

                // Hover highlight
                if (mouseX >= panelX && mouseX <= panelX + PANEL_W
                        && mouseY >= rowY && mouseY <= rowY + ROW_H) {
                    NVGRenderer.roundedRect(panelX + 4, rowY, PANEL_W - 8, ROW_H, 4, HOVER_BG, 1f);
                }

                // Toggle switch
                float toggleX = panelX + PANEL_W - TOGGLE_W - 16;
                float toggleY = rowY + (ROW_H - TOGGLE_H) / 2;
                float t = toggleAnim[i];

                // Toggle bg — interpolate off→on color
                int bgColor = lerpColor(TOGGLE_OFF, TOGGLE_ON, t);
                NVGRenderer.roundedRect(toggleX, toggleY, TOGGLE_W, TOGGLE_H, TOGGLE_H / 2, bgColor, 1f);

                // Knob (circle)
                float knobR = (TOGGLE_H - 4) / 2f;
                float knobCX = toggleX + 2 + knobR + t * (TOGGLE_W - 4 - knobR * 2);
                float knobCY = toggleY + TOGGLE_H / 2f;
                // Knob shadow
                NVGRenderer.circle(knobCX + 0.5f, knobCY + 0.5f, knobR + 0.5f, 0xFF000000, 0.2f);
                // Knob
                NVGRenderer.circle(knobCX, knobCY, knobR, TOGGLE_KNOB, 1f);
            }

            // NVG text (if font available)
            if (NVGRenderer.hasFont()) {
                NVGRenderer.textCentered("SkyAI Settings", panelX + PANEL_W / 2, py + 16, 16, TEXT_PRIMARY, 1f);
                NVGRenderer.textCentered("v" + HypixelAIUpdater.MOD_VERSION, panelX + PANEL_W / 2, py + 38, 11, TEXT_DIM, 1f);

                for (int i = 0; i < SETTINGS.length; i++) {
                    float rowY = rowsStartY + i * ROW_H;
                    NVGRenderer.text(SETTINGS[i][1], panelX + 16, rowY + 5, 13, TEXT_PRIMARY, 1f);
                    NVGRenderer.text(SETTINGS[i][2], panelX + 16, rowY + 19, 11, TEXT_DIM, 1f);
                }

                float footerY = rowsStartY + SETTINGS.length * ROW_H + 10;
                NVGRenderer.textCentered("Click to toggle \u2022 ESC to close",
                        panelX + PANEL_W / 2, footerY, 11, TEXT_DIM, 1f);
            }

            NVGRenderer.endFrame();

            // MC text fallback (when NVG font not loaded)
            if (!NVGRenderer.hasFont()) {
                drawTextWithMC(ctx, rowsStartY);
            }
        } else {
            // ========== FALLBACK (no NVG) ==========
            ctx.fill(0, 0, width, height, 0xCC000000);
            int px = (int) panelX;
            ctx.fill(px - 1, (int) py - 1, px + (int) PANEL_W + 1, (int) (py + totalH) + 1, CARD_BORDER & 0xFFFFFFFF);
            ctx.fill(px, (int) py, px + (int) PANEL_W, (int) (py + totalH), CARD_BG & 0xFFFFFFFF);
            drawTextWithMC(ctx, rowsStartY);
        }
    }

    private void drawTextWithMC(DrawContext ctx, float rowsStartY) {
        var tr = textRenderer;
        int cx = (int) (panelX + PANEL_W / 2);

        String title = "SkyAI Settings";
        ctx.drawText(tr, title, cx - tr.getWidth(title) / 2, (int) panelY + 16, TEXT_PRIMARY, false);

        String ver = "v" + HypixelAIUpdater.MOD_VERSION;
        ctx.drawText(tr, ver, cx - tr.getWidth(ver) / 2, (int) panelY + 38, TEXT_DIM, false);

        for (int i = 0; i < SETTINGS.length; i++) {
            int rowY = (int) (rowsStartY + i * ROW_H);
            ctx.drawText(tr, SETTINGS[i][1], (int) panelX + 16, rowY + 5, TEXT_PRIMARY, false);
            ctx.drawText(tr, SETTINGS[i][2], (int) panelX + 16, rowY + 19, TEXT_DIM, false);
        }

        float footerY = rowsStartY + SETTINGS.length * ROW_H + 10;
        String footer = "Click to toggle \u2022 ESC to close";
        ctx.drawText(tr, footer, cx - tr.getWidth(footer) / 2, (int) footerY, TEXT_DIM, false);
    }

    @Override
    public boolean mouseClicked(Click click, boolean bl) {
        if (click.button() == 0) {
            double mouseX = click.x();
            double mouseY = click.y();
            float rowsStartY = panelY + 68;

            for (int i = 0; i < SETTINGS.length; i++) {
                float rowY = rowsStartY + i * ROW_H;
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

    private static int lerpColor(int from, int to, float t) {
        int r = (int) (((from >> 16) & 0xFF) + (((to >> 16) & 0xFF) - ((from >> 16) & 0xFF)) * t);
        int g = (int) (((from >> 8) & 0xFF) + (((to >> 8) & 0xFF) - ((from >> 8) & 0xFF)) * t);
        int b = (int) ((from & 0xFF) + ((to & 0xFF) - (from & 0xFF)) * t);
        int a = (int) (((from >> 24) & 0xFF) + (((to >> 24) & 0xFF) - ((from >> 24) & 0xFF)) * t);
        return (a << 24) | (r << 16) | (g << 8) | b;
    }
}
