package com.hypixelai;

import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.render.RenderTickCounter;
import net.minecraft.entity.player.PlayerEntity;

/**
 * Cortisol meter — replaces the vanilla health bar with a gradient bar.
 * Green (full) → Yellow (mid) → Red (low).
 * Renders in the same spot as vanilla hearts (bottom left, above hotbar).
 */
public class CortisolBar implements HudRenderCallback {

    private static final int BAR_WIDTH = 81;  // Same width as 10 hearts (8px each + 1px gap)
    private static final int BAR_HEIGHT = 5;
    private static final int BG_HEIGHT = 9;   // Background height to cover hearts
    private static final int LABEL_OFFSET_Y = -10;

    // Colors
    private static final int BG_COLOR = 0xFF0a0a18;
    private static final int BG_BORDER = 0xFF16162a;
    private static final int LABEL_COLOR = 0xFF8892a8;

    // Smooth animation
    private static float displayedHealth = 20f;
    private static float displayedMaxHealth = 20f;

    public static void register() {
        HudRenderCallback.EVENT.register(new CortisolBar());
    }

    @Override
    public void onHudRender(DrawContext ctx, RenderTickCounter tickCounter) {
        MinecraftClient client = MinecraftClient.getInstance();
        if (client == null || client.player == null || client.options.hudHidden) return;

        PlayerEntity player = client.player;
        float health = player.getHealth();
        float maxHealth = player.getMaxHealth();
        float absorption = player.getAbsorptionAmount();

        // Smooth animation
        displayedHealth += (health - displayedHealth) * 0.15f;
        displayedMaxHealth = maxHealth;

        // Cortisol is INVERTED: full health = 0, dying = 20
        // healthRatio: 1.0 = full HP, 0.0 = dead
        float healthRatio = Math.max(0, Math.min(1, displayedHealth / Math.max(maxHealth, 1)));
        // cortisol: 0 = calm (full HP), 20 = max stress (dying)
        float cortisol = 20f * (1f - healthRatio);
        // barRatio: how full the bar is (0 = empty/calm, 1 = full/dying)
        float barRatio = cortisol / 20f;

        // Smooth the displayed cortisol
        float displayCortisol = Math.round(cortisol * 10f) / 10f;

        int screenW = ctx.getScaledWindowWidth();
        int screenH = ctx.getScaledWindowHeight();

        // Position: same as vanilla hearts — left of center, above hotbar
        int heartX = screenW / 2 - 91;
        int heartY = screenH - 39;

        // Cover vanilla hearts with background
        ctx.fill(heartX - 1, heartY - 1, heartX + BAR_WIDTH + 1, heartY + BG_HEIGHT + 1, BG_COLOR);

        // Draw bar background (dark)
        int barX = heartX;
        int barY = heartY + 2;
        ctx.fill(barX - 1, barY - 1, barX + BAR_WIDTH + 1, barY + BAR_HEIGHT + 1, BG_BORDER);
        ctx.fill(barX, barY, barX + BAR_WIDTH, barY + BAR_HEIGHT, 0xFF060612);

        // Draw filled portion — bar fills up as you take damage
        int filledWidth = (int) (BAR_WIDTH * barRatio);
        if (filledWidth > 0) {
            for (int i = 0; i < filledWidth; i++) {
                float pixelRatio = (float) i / BAR_WIDTH;
                int color = getStressColor(pixelRatio);
                ctx.fill(barX + i, barY, barX + i + 1, barY + BAR_HEIGHT, color);
            }

            // Subtle highlight on top edge
            for (int i = 0; i < filledWidth; i++) {
                float pixelT = (float) i / Math.max(filledWidth, 1);
                int highlight = ((int)(15 * (1f - pixelT)) << 24) | 0x00FFFFFF;
                ctx.fill(barX + i, barY, barX + i + 1, barY + 1, highlight);
            }
        }

        // Pulsing glow when cortisol is high (low health)
        if (barRatio > 0.7f) {
            long pulse = System.currentTimeMillis() % 800;
            float pulseAlpha = (float) (Math.sin(pulse / 800.0 * Math.PI * 2) * 0.35 + 0.35);
            int glowAlpha = (int) (pulseAlpha * 255 * barRatio);
            int glow = (glowAlpha << 24) | 0x00FF0000;
            ctx.fill(barX - 2, barY - 2, barX + BAR_WIDTH + 2, barY + BAR_HEIGHT + 2, glow);
        }

        // Label
        TextRenderer tr = client.textRenderer;
        String label = "CORTISOL";
        int labelX = heartX;
        int labelY = heartY + LABEL_OFFSET_Y;
        int labelColor = barRatio > 0.7f ? getStressColor(barRatio) : LABEL_COLOR;
        ctx.drawText(tr, label, labelX, labelY, labelColor, false);

        // Cortisol value (right-aligned) — shows 0.0 to 20.0
        String valueText = String.format("%.1f / 20", displayCortisol);
        int valueWidth = tr.getWidth(valueText);
        ctx.drawText(tr, valueText, heartX + BAR_WIDTH - valueWidth, labelY, getStressColor(barRatio), false);
    }

    /**
     * Get color based on stress level.
     * 0.0 = calm (green), 0.5 = moderate (yellow), 1.0 = max stress (red)
     */
    private static int getStressColor(float stress) {
        int r, g, b;
        if (stress < 0.5f) {
            // Green to Yellow (0.0 → 0.5)
            float t = stress * 2;
            r = (int) (255 * t);
            g = 255;
            b = 0;
        } else {
            // Yellow to Red (0.5 → 1.0)
            float t = (stress - 0.5f) * 2;
            r = 255;
            g = (int) (255 * (1 - t));
            b = 0;
        }
        return 0xFF000000 | (r << 16) | (g << 8) | b;
    }
}
