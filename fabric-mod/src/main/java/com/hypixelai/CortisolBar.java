package com.hypixelai;

import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.render.RenderTickCounter;
import net.minecraft.entity.player.PlayerEntity;

/**
 * Cortisol meter — speedometer/gauge style semi-circle.
 * Needle sweeps from left (0 = calm) to right (20 = dying).
 * Arc goes green → yellow → orange → red.
 */
public class CortisolBar implements HudRenderCallback {

    // Gauge dimensions — bigger and higher
    private static final int RADIUS = 38;
    private static final int ARC_THICKNESS = 6;
    private static final int NEEDLE_LEN = 30;
    private static final int ARC_SEGMENTS = 50;

    // Smooth animation
    private static float displayedHealth = 20f;

    // Colors
    private static final int BG_COLOR = 0x00000000; // transparent — no background arc
    private static final int TICK_COLOR = 0xFF333355;
    private static final int LABEL_COLOR = 0xFFaaaacc;
    private static final int LABEL_DIM = 0xFF555577;
    private static final int NEEDLE_COLOR = 0xFFe2e2f0;
    private static final int NEEDLE_SHADOW = 0xFF222244;
    private static final int CENTER_DOT = 0xFF888899;

    public static void register() {
        HudRenderCallback.EVENT.register(new CortisolBar());
    }

    @Override
    public void onHudRender(DrawContext ctx, RenderTickCounter tickCounter) {
        MinecraftClient client = MinecraftClient.getInstance();
        if (client == null || client.player == null || client.options.hudHidden) return;
        if (!HypixelAIConfig.isCortisolBar()) return;

        PlayerEntity player = client.player;
        float health = player.getHealth();
        float maxHealth = player.getMaxHealth();
        float absorption = player.getAbsorptionAmount();
        float totalHealth = health + absorption;

        // Smooth animation
        displayedHealth += (totalHealth - displayedHealth) * 0.1f;

        // Cortisol: 0 = calm (full HP), 20 = dying, negative = overflow (absorption/overheal)
        // At full HP: cortisol = 0. Below max: cortisol = positive. Above max (absorption): cortisol = negative.
        float cortisol = 20f * (1f - displayedHealth / Math.max(maxHealth, 1));
        float displayCortisol = Math.round(cortisol * 10f) / 10f;

        // barRatio: 0-1 for the main gauge (0=calm, 1=dying)
        float barRatio = Math.max(0, Math.min(1, cortisol / 20f));

        // overflowRatio: how far into negative (0 = no overflow, 1 = max overflow display)
        float overflowRatio = cortisol < 0 ? Math.min(1f, -cortisol / 20f) : 0f;

        int screenW = ctx.getScaledWindowWidth();
        int screenH = ctx.getScaledWindowHeight();

        // Position: dead center above hotbar
        int centerX = screenW / 2;
        int centerY = screenH - 55;

        // === Draw overflow arc (left side, for absorption/overheal) ===
        if (overflowRatio > 0) {
            // Overflow extends from 180° backwards (leftward/downward)
            int overflowSegs = (int) (ARC_SEGMENTS * 0.4f); // max 40% extra arc
            int filledOverflow = (int) (overflowSegs * overflowRatio);
            for (int i = 0; i < filledOverflow; i++) {
                float segStart = (float) i / overflowSegs;
                float segEnd = (float) (i + 1) / overflowSegs;
                // Draw below the left side: from 180° going to 180°+90° (downward)
                float a1 = 0.0f - segEnd * 0.4f; // negative = before the 0 mark
                float a2 = 0.0f - segStart * 0.4f;
                int color = getOverflowColor(segStart);
                fillArc(ctx, centerX, centerY, RADIUS, ARC_THICKNESS, a1, a2, color);
            }
        }

        // === Draw main colored arc segments ===
        for (int i = 0; i < ARC_SEGMENTS; i++) {
            float segStart = (float) i / ARC_SEGMENTS;
            float segEnd = (float) (i + 1) / ARC_SEGMENTS;

            int color;
            if (segStart <= barRatio) {
                color = getStressColor(segStart);
            } else {
                color = 0xFF1a1a28; // unfilled segment (dark)
            }
            fillArc(ctx, centerX, centerY, RADIUS, ARC_THICKNESS, segStart, segEnd, color);
        }

        // === Draw tick marks around the arc ===
        for (int i = 0; i <= 10; i++) {
            float t = (float) i / 10;
            double angle = Math.PI + t * Math.PI;
            int tickInner = RADIUS - ARC_THICKNESS - 2;
            int tickOuter = RADIUS - ARC_THICKNESS - (i % 5 == 0 ? 5 : 3);

            int tx1 = centerX + (int) (Math.cos(angle) * tickInner);
            int ty1 = centerY + (int) (Math.sin(angle) * tickInner);
            int tx2 = centerX + (int) (Math.cos(angle) * tickOuter);
            int ty2 = centerY + (int) (Math.sin(angle) * tickOuter);

            ctx.fill(Math.min(tx1, tx2), Math.min(ty1, ty2),
                     Math.max(tx1, tx2) + 1, Math.max(ty1, ty2) + 1, TICK_COLOR);
        }

        // === Draw needle ===
        // Needle can go past 0 into negative for overflow
        float needleRatio;
        if (cortisol >= 0) {
            needleRatio = barRatio; // 0-1 maps to left-right
        } else {
            // Negative cortisol: needle goes past left into overflow zone
            needleRatio = -overflowRatio * 0.4f; // extends left
        }
        double needleAngle = Math.PI + needleRatio * Math.PI;
        int nx = centerX + (int) (Math.cos(needleAngle) * NEEDLE_LEN);
        int ny = centerY + (int) (Math.sin(needleAngle) * NEEDLE_LEN);

        drawLine(ctx, centerX + 1, centerY + 1, nx + 1, ny + 1, NEEDLE_SHADOW);
        int needleCol;
        if (cortisol < 0) {
            needleCol = getOverflowColor(overflowRatio);
        } else if (barRatio > 0.7f) {
            needleCol = getStressColor(barRatio);
        } else {
            needleCol = NEEDLE_COLOR;
        }
        drawLine(ctx, centerX, centerY, nx, ny, needleCol);

        // Center dot
        ctx.fill(centerX - 2, centerY - 2, centerX + 3, centerY + 3, CENTER_DOT);
        ctx.fill(centerX - 1, centerY - 1, centerX + 2, centerY + 2, 0xFF000000);

        // === Text ===
        TextRenderer tr = client.textRenderer;

        // Cortisol value centered below gauge
        String val = String.format("%.1f", displayCortisol);
        int valW = tr.getWidth(val);
        int valColor;
        if (cortisol < 0) {
            valColor = getOverflowColor(overflowRatio);
        } else {
            valColor = getStressColor(barRatio);
        }
        ctx.drawText(tr, val, centerX - valW / 2, centerY + 3, valColor, false);

        // "0" on left, "20" on right
        ctx.drawText(tr, "0", centerX - RADIUS - 10, centerY - 4, LABEL_DIM, false);
        ctx.drawText(tr, "20", centerX + RADIUS + 3, centerY - 4, LABEL_DIM, false);

        // "CORTISOL" label above
        String label = "CORTISOL";
        int lblW = tr.getWidth(label);
        int lblColor;
        if (cortisol < 0) {
            lblColor = getOverflowColor(overflowRatio);
        } else if (barRatio > 0.6f) {
            lblColor = getStressColor(barRatio);
        } else {
            lblColor = LABEL_COLOR;
        }
        ctx.drawText(tr, label, centerX - lblW / 2, centerY - RADIUS - 10, lblColor, false);

        // === Pulsing glow when high stress ===
        if (barRatio > 0.7f) {
            long t = System.currentTimeMillis() % 1000;
            float pulse = (float) (Math.sin(t / 1000.0 * Math.PI * 2) * 0.2 + 0.2);
            int alpha = (int) (pulse * 180 * barRatio);
            int glow = (Math.min(alpha, 255) << 24) | 0x00FF2020;
            fillArc(ctx, centerX, centerY, RADIUS + 4, ARC_THICKNESS + 8, 0, barRatio, glow);
        }
    }

    /**
     * Overflow color: cyan to blue (for absorption/overheal).
     * 0.0 = light cyan, 1.0 = deep blue
     */
    private static int getOverflowColor(float t) {
        int r = (int) (20 + 30 * (1 - t));
        int g = (int) (200 + 55 * (1 - t));
        int b = (int) (220 + 35 * (1 - t));
        return 0xFF000000 | (cl(r) << 16) | (cl(g) << 8) | cl(b);
    }

    /**
     * Draw a filled arc segment (semi-circle, top half).
     * ratio 0 = left (180°), ratio 1 = right (0°/360°)
     */
    private static void fillArc(DrawContext ctx, int cx, int cy, int radius, int thickness,
                                 float startRatio, float endRatio, int color) {
        int steps = 30;
        for (int i = 0; i < steps; i++) {
            float t1 = startRatio + (endRatio - startRatio) * i / steps;
            float t2 = startRatio + (endRatio - startRatio) * (i + 1) / steps;

            double a1 = Math.PI + t1 * Math.PI;
            double a2 = Math.PI + t2 * Math.PI;

            // Outer edge
            int ox1 = cx + (int) (Math.cos(a1) * radius);
            int oy1 = cy + (int) (Math.sin(a1) * radius);
            int ox2 = cx + (int) (Math.cos(a2) * radius);
            int oy2 = cy + (int) (Math.sin(a2) * radius);

            // Inner edge
            int ix1 = cx + (int) (Math.cos(a1) * (radius - thickness));
            int iy1 = cy + (int) (Math.sin(a1) * (radius - thickness));
            int ix2 = cx + (int) (Math.cos(a2) * (radius - thickness));
            int iy2 = cy + (int) (Math.sin(a2) * (radius - thickness));

            // Fill as a small rect (approximation that works for small arc segments)
            int minX = Math.min(Math.min(ox1, ox2), Math.min(ix1, ix2));
            int maxX = Math.max(Math.max(ox1, ox2), Math.max(ix1, ix2));
            int minY = Math.min(Math.min(oy1, oy2), Math.min(iy1, iy2));
            int maxY = Math.max(Math.max(oy1, oy2), Math.max(iy1, iy2));

            if (maxX > minX && maxY > minY) {
                ctx.fill(minX, minY, maxX, maxY, color);
            }
        }
    }

    /**
     * Draw a line using small filled rects (Bresenham-ish).
     */
    private static void drawLine(DrawContext ctx, int x0, int y0, int x1, int y1, int color) {
        int dx = Math.abs(x1 - x0);
        int dy = Math.abs(y1 - y0);
        int sx = x0 < x1 ? 1 : -1;
        int sy = y0 < y1 ? 1 : -1;
        int err = dx - dy;

        while (true) {
            ctx.fill(x0, y0, x0 + 1, y0 + 1, color);
            if (x0 == x1 && y0 == y1) break;
            int e2 = 2 * err;
            if (e2 > -dy) { err -= dy; x0 += sx; }
            if (e2 < dx) { err += dx; y0 += sy; }
        }
    }

    /**
     * Stress color: 0.0=green, 0.5=yellow/orange, 1.0=red
     */
    private static int getStressColor(float stress) {
        int r, g, b;
        if (stress < 0.35f) {
            float t = stress / 0.35f;
            r = (int) (30 + 225 * t);
            g = (int) (200 + 55 * (1 - t));
            b = (int) (40 * (1 - t));
        } else if (stress < 0.65f) {
            float t = (stress - 0.35f) / 0.3f;
            r = 255;
            g = (int) (230 - 130 * t);
            b = 0;
        } else {
            float t = (stress - 0.65f) / 0.35f;
            r = 255;
            g = (int) (100 - 100 * t);
            b = (int) (30 * t);
        }
        return 0xFF000000 | (cl(r) << 16) | (cl(g) << 8) | cl(b);
    }

    private static int cl(int v) { return Math.max(0, Math.min(255, v)); }
}
