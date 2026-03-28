package com.hypixelai;

import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.render.RenderTickCounter;
import net.minecraft.entity.player.PlayerEntity;

/**
 * Cortisol meter — replaces vanilla health hearts with a modern stress bar.
 * Inverted: 0 = calm (full HP), 20 = max stress (dying).
 * Wide bar with segments, gradient fill, label + value display.
 */
public class CortisolBar implements HudRenderCallback {

    // Bar dimensions — wider and thicker than vanilla hearts
    private static final int BAR_WIDTH = 100;
    private static final int BAR_HEIGHT = 8;
    private static final int COVER_W = 100;  // Width to cover vanilla hearts
    private static final int COVER_H = 12;   // Height to cover vanilla hearts

    // Segment count for the segmented look
    private static final int SEGMENTS = 20;

    // Colors
    private static final int BG_DARK = 0xFF080810;
    private static final int BG_BORDER = 0xFF1a1a2e;
    private static final int BG_INNER = 0xFF0c0c18;
    private static final int LABEL_COLOR = 0xFFaaaacc;
    private static final int LABEL_DIM = 0xFF555577;
    private static final int SEG_GAP_COLOR = 0xFF0a0a14;

    // Smooth animation
    private static float displayedHealth = 20f;

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

        // Smooth animation
        displayedHealth += (health - displayedHealth) * 0.12f;

        // Cortisol: 0 = calm, 20 = dying
        float healthRatio = Math.max(0, Math.min(1, displayedHealth / Math.max(maxHealth, 1)));
        float cortisol = 20f * (1f - healthRatio);
        float barRatio = Math.max(0, Math.min(1, cortisol / 20f));
        float displayCortisol = Math.round(cortisol * 10f) / 10f;

        int screenW = ctx.getScaledWindowWidth();
        int screenH = ctx.getScaledWindowHeight();

        // Position — same area as vanilla hearts
        int baseX = screenW / 2 - 91;
        int baseY = screenH - 40;

        // === Cover vanilla hearts ===
        ctx.fill(baseX - 2, baseY - 12, baseX + COVER_W + 2, baseY + COVER_H + 2, BG_DARK);

        // === Label row: "CORTISOL" left, "12.5 / 20" right ===
        TextRenderer tr = client.textRenderer;
        int labelY = baseY - 10;

        // Label color shifts with stress
        int lColor = barRatio > 0.6f ? getStressColor(barRatio) : LABEL_COLOR;
        ctx.drawText(tr, "CORTISOL", baseX, labelY, lColor, false);

        // Value
        String val = String.format("%.1f", displayCortisol);
        String max = " / 20";
        int valColor = getStressColor(barRatio);
        int valW = tr.getWidth(val);
        int maxW = tr.getWidth(max);
        ctx.drawText(tr, val, baseX + BAR_WIDTH - valW - maxW, labelY, valColor, false);
        ctx.drawText(tr, max, baseX + BAR_WIDTH - maxW, labelY, LABEL_DIM, false);

        // === Bar background ===
        int barX = baseX;
        int barY = baseY + 1;

        // Outer border
        ctx.fill(barX - 1, barY - 1, barX + BAR_WIDTH + 1, barY + BAR_HEIGHT + 1, BG_BORDER);
        // Inner background
        ctx.fill(barX, barY, barX + BAR_WIDTH, barY + BAR_HEIGHT, BG_INNER);

        // === Filled segments ===
        int filledWidth = (int) (BAR_WIDTH * barRatio);
        int segW = BAR_WIDTH / SEGMENTS; // 5px per segment

        for (int s = 0; s < SEGMENTS; s++) {
            int sx = barX + s * segW;
            int sw = segW - 1; // 1px gap between segments
            int segEnd = sx + sw;

            if (sx >= barX + filledWidth) break; // Past the filled area

            // Clamp to filled width
            if (segEnd > barX + filledWidth) {
                sw = (barX + filledWidth) - sx;
                if (sw <= 0) break;
            }

            // Color based on segment position
            float segRatio = (float) s / SEGMENTS;
            int color = getStressColor(segRatio);

            // Main fill
            ctx.fill(sx, barY, sx + sw, barY + BAR_HEIGHT, color);

            // Top highlight (lighter)
            int highlight = brighten(color, 40);
            ctx.fill(sx, barY, sx + sw, barY + 1, highlight);

            // Bottom shadow (darker)
            int shadow = darken(color, 30);
            ctx.fill(sx, barY + BAR_HEIGHT - 1, sx + sw, barY + BAR_HEIGHT, shadow);
        }

        // === Pulsing red glow when high stress ===
        if (barRatio > 0.7f) {
            long t = System.currentTimeMillis() % 1000;
            float pulse = (float) (Math.sin(t / 1000.0 * Math.PI * 2) * 0.3 + 0.3);
            int alpha = (int) (pulse * 200 * barRatio);
            int glow = (Math.min(alpha, 255) << 24) | 0x00FF2020;
            ctx.fill(barX - 2, barY - 2, barX + BAR_WIDTH + 2, barY + BAR_HEIGHT + 2, glow);
        }

        // === Segment divider lines (on top of everything for crisp look) ===
        for (int s = 1; s < SEGMENTS; s++) {
            int lx = barX + s * segW - 1;
            ctx.fill(lx, barY, lx + 1, barY + BAR_HEIGHT, SEG_GAP_COLOR);
        }
    }

    /**
     * Stress color: 0.0=green, 0.5=yellow, 1.0=red
     */
    private static int getStressColor(float stress) {
        int r, g, b;
        if (stress < 0.4f) {
            // Green to Yellow
            float t = stress / 0.4f;
            r = (int) (50 + 205 * t);
            g = (int) (220 + 35 * (1 - t));
            b = (int) (30 * (1 - t));
        } else if (stress < 0.7f) {
            // Yellow to Orange
            float t = (stress - 0.4f) / 0.3f;
            r = 255;
            g = (int) (220 - 120 * t);
            b = 0;
        } else {
            // Orange to Red
            float t = (stress - 0.7f) / 0.3f;
            r = 255;
            g = (int) (100 - 100 * t);
            b = (int) (20 * t);
        }
        return 0xFF000000 | (clamp(r) << 16) | (clamp(g) << 8) | clamp(b);
    }

    private static int brighten(int color, int amount) {
        int r = Math.min(255, ((color >> 16) & 0xFF) + amount);
        int g = Math.min(255, ((color >> 8) & 0xFF) + amount);
        int b = Math.min(255, (color & 0xFF) + amount);
        return 0xFF000000 | (r << 16) | (g << 8) | b;
    }

    private static int darken(int color, int amount) {
        int r = Math.max(0, ((color >> 16) & 0xFF) - amount);
        int g = Math.max(0, ((color >> 8) & 0xFF) - amount);
        int b = Math.max(0, (color & 0xFF) - amount);
        return 0xFF000000 | (r << 16) | (g << 8) | b;
    }

    private static int clamp(int v) {
        return Math.max(0, Math.min(255, v));
    }
}
