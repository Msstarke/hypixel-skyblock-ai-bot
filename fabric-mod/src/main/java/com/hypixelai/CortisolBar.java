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

        float totalMax = maxHealth + absorption;
        float totalCurrent = displayedHealth + absorption;
        float ratio = Math.max(0, Math.min(1, totalCurrent / totalMax));

        int screenW = ctx.getScaledWindowWidth();
        int screenH = ctx.getScaledWindowHeight();

        // Position: same as vanilla hearts — left of center, above hotbar
        // Vanilla hearts are at: x = screenW/2 - 91, y = screenH - 39
        int heartX = screenW / 2 - 91;
        int heartY = screenH - 39;

        // Cover vanilla hearts with background
        ctx.fill(heartX - 1, heartY - 1, heartX + BAR_WIDTH + 1, heartY + BG_HEIGHT + 1, BG_COLOR);

        // Draw bar background (dark)
        int barX = heartX;
        int barY = heartY + 2;
        ctx.fill(barX - 1, barY - 1, barX + BAR_WIDTH + 1, barY + BAR_HEIGHT + 1, BG_BORDER);
        ctx.fill(barX, barY, barX + BAR_WIDTH, barY + BAR_HEIGHT, 0xFF060612);

        // Draw filled portion with gradient
        int filledWidth = (int) (BAR_WIDTH * ratio);
        if (filledWidth > 0) {
            for (int i = 0; i < filledWidth; i++) {
                float t = (float) i / BAR_WIDTH; // 0 = left (low), 1 = right (full)
                // But we want: left = start of bar, right = current health
                // Color based on overall health ratio, not pixel position
                int color = getGradientColor(ratio);
                ctx.fill(barX + i, barY, barX + i + 1, barY + BAR_HEIGHT, color);
            }

            // Add a subtle gradient across the filled bar for depth
            for (int i = 0; i < filledWidth; i++) {
                float pixelT = (float) i / Math.max(filledWidth, 1);
                int highlight = ((int)(20 * pixelT) << 24) | 0x00FFFFFF; // subtle white gradient
                ctx.fill(barX + i, barY, barX + i + 1, barY + 1, highlight);
            }
        }

        // Glow effect when low health
        if (ratio < 0.3f) {
            long pulse = System.currentTimeMillis() % 1000;
            float pulseAlpha = (float) (Math.sin(pulse / 1000.0 * Math.PI * 2) * 0.3 + 0.3);
            int glowAlpha = (int) (pulseAlpha * 255);
            int glow = (glowAlpha << 24) | 0x00FF0000;
            ctx.fill(barX - 2, barY - 2, barX + BAR_WIDTH + 2, barY + BAR_HEIGHT + 2, glow);
        }

        // Label
        TextRenderer tr = client.textRenderer;
        String label = "CORTISOL";
        int labelX = heartX;
        int labelY = heartY + LABEL_OFFSET_Y;
        ctx.drawText(tr, label, labelX, labelY, LABEL_COLOR, false);

        // Health text (right-aligned)
        String healthText = String.format("%.0f/%.0f", Math.max(0, displayedHealth + absorption), totalMax);
        int healthTextWidth = tr.getWidth(healthText);
        ctx.drawText(tr, healthText, heartX + BAR_WIDTH - healthTextWidth, labelY, getGradientColor(ratio), false);
    }

    /**
     * Get color based on health ratio.
     * 1.0 = full (green), 0.5 = mid (yellow), 0.0 = empty (red)
     */
    private static int getGradientColor(float ratio) {
        int r, g, b;
        if (ratio > 0.5f) {
            // Green to Yellow (1.0 → 0.5)
            float t = (ratio - 0.5f) * 2; // 1→0
            r = (int) (255 * (1 - t));
            g = 255;
            b = (int) (50 * t);
        } else {
            // Yellow to Red (0.5 → 0.0)
            float t = ratio * 2; // 1→0
            r = 255;
            g = (int) (255 * t);
            b = 0;
        }
        return 0xFF000000 | (r << 16) | (g << 8) | b;
    }
}
