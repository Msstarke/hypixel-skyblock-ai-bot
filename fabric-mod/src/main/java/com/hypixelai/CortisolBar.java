package com.hypixelai;

import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.render.RenderTickCounter;
import net.minecraft.entity.player.PlayerEntity;

/**
 * Cortisol meter — speedometer/gauge style semi-circle.
 * NanoVG rendered — proper anti-aliased arcs, smooth needle, blur glow.
 * Needle sweeps from left (0 = calm) to right (20 = dying).
 */
public class CortisolBar implements HudRenderCallback {

    private static final int RADIUS = 38;
    private static final int ARC_THICKNESS = 6;
    private static final int NEEDLE_LEN = 30;
    private static final int ARC_SEGMENTS = 50;

    private static float displayedHealth = 20f;

    // Colors
    private static final int TICK_COLOR = 0xFF333355;
    private static final int LABEL_COLOR = 0xFFaaaacc;
    private static final int LABEL_DIM = 0xFF555577;
    private static final int NEEDLE_COLOR = 0xFFe2e2f0;
    private static final int NEEDLE_SHADOW = 0xFF222244;
    private static final int CENTER_DOT = 0xFF888899;
    private static final int UNFILLED = 0xFF1a1a28;

    public static void register() {
        HudRenderCallback.EVENT.register(new CortisolBar());
    }

    @Override
    public void onHudRender(DrawContext ctx, RenderTickCounter tickCounter) {
        MinecraftClient client = MinecraftClient.getInstance();
        if (client == null || client.player == null || client.options.hudHidden) return;
        if (!HypixelAIConfig.isCortisolBar()) return;
        // Don't render when a screen is open (inventory, chat, etc.)
        if (client.currentScreen != null) return;

        PlayerEntity player = client.player;
        float health = player.getHealth();
        float maxHealth = player.getMaxHealth();
        float absorption = player.getAbsorptionAmount();
        float totalHealth = health + absorption;

        // Smooth animation
        displayedHealth += (totalHealth - displayedHealth) * 0.1f;

        // Cortisol: 0 = calm (full HP), 20 = dying. Negative = overflow (absorption)
        float cortisol = 20f * (1f - displayedHealth / Math.max(maxHealth, 1));
        float displayCortisol = Math.round(cortisol * 10f) / 10f;
        float barRatio = Math.max(0, Math.min(1, cortisol / 20f));
        float overflowRatio = cortisol < 0 ? Math.min(1f, -cortisol / 20f) : 0f;

        int screenW = ctx.getScaledWindowWidth();
        int screenH = ctx.getScaledWindowHeight();
        float centerX = screenW / 2f;
        float centerY = screenH - 55f;

        TextRenderer tr = client.textRenderer;

        // Initialize NVG on first render
        if (!NVGRenderer.isReady()) {
            NVGRenderer.init();
        }

        if (NVGRenderer.isReady()) {
            renderNVG(ctx, tr, centerX, centerY, barRatio, overflowRatio, cortisol, displayCortisol);
        } else {
            renderLegacy(ctx, tr, centerX, centerY, barRatio, overflowRatio, cortisol, displayCortisol);
        }
    }

    private void renderNVG(DrawContext ctx, TextRenderer tr, float centerX, float centerY,
                           float barRatio, float overflowRatio, float cortisol, float displayCortisol) {
        NVGRenderer.beginFrame();

        // === Overflow arc (absorption — extends left from the 0 mark) ===
        if (overflowRatio > 0) {
            int overflowSegs = (int) (ARC_SEGMENTS * 0.4f);
            int filledOverflow = (int) (overflowSegs * overflowRatio);
            for (int i = 0; i < filledOverflow; i++) {
                float segStart = (float) i / overflowSegs;
                float segEnd = (float) (i + 1) / overflowSegs;
                float a1 = (float) Math.PI - segEnd * 0.4f * (float) Math.PI;
                float a2 = (float) Math.PI - segStart * 0.4f * (float) Math.PI;
                int color = getOverflowColor(segStart);
                NVGRenderer.arc(centerX, centerY, RADIUS, ARC_THICKNESS, a1, a2, color, 1f);
            }
        }

        // === Main colored arc (left=calm, right=dying) ===
        for (int i = 0; i < ARC_SEGMENTS; i++) {
            float segStart = (float) i / ARC_SEGMENTS;
            float segEnd = (float) (i + 1) / ARC_SEGMENTS;
            float a1 = (float) Math.PI + segStart * (float) Math.PI;
            float a2 = (float) Math.PI + segEnd * (float) Math.PI;
            int color = segStart <= barRatio ? getStressColor(segStart) : UNFILLED;
            NVGRenderer.arc(centerX, centerY, RADIUS, ARC_THICKNESS, a1, a2, color, 1f);
        }

        // === Tick marks ===
        for (int i = 0; i <= 10; i++) {
            float t = (float) i / 10;
            double angle = Math.PI + t * Math.PI;
            float innerR = RADIUS - ARC_THICKNESS - 2;
            float outerR = RADIUS - ARC_THICKNESS - (i % 5 == 0 ? 5 : 3);
            float tx1 = centerX + (float) Math.cos(angle) * innerR;
            float ty1 = centerY + (float) Math.sin(angle) * innerR;
            float tx2 = centerX + (float) Math.cos(angle) * outerR;
            float ty2 = centerY + (float) Math.sin(angle) * outerR;
            NVGRenderer.line(tx1, ty1, tx2, ty2, 1f, TICK_COLOR, 1f);
        }

        // === Needle ===
        float needleRatio = cortisol >= 0 ? barRatio : -overflowRatio * 0.4f;
        double needleAngle = Math.PI + needleRatio * Math.PI;
        float nx = centerX + (float) Math.cos(needleAngle) * NEEDLE_LEN;
        float ny = centerY + (float) Math.sin(needleAngle) * NEEDLE_LEN;

        // Needle shadow
        NVGRenderer.line(centerX + 1, centerY + 1, nx + 1, ny + 1, 2f, NEEDLE_SHADOW, 0.6f);

        // Needle line
        int needleCol;
        if (cortisol < 0) needleCol = getOverflowColor(overflowRatio);
        else if (barRatio > 0.7f) needleCol = getStressColor(barRatio);
        else needleCol = NEEDLE_COLOR;
        NVGRenderer.line(centerX, centerY, nx, ny, 1.5f, needleCol, 1f);

        // Center dot
        NVGRenderer.circle(centerX, centerY, 3, CENTER_DOT, 1f);
        NVGRenderer.circle(centerX, centerY, 1.5f, 0xFF000000, 1f);

        // === Pulsing glow when high stress ===
        if (barRatio > 0.7f) {
            long t = System.currentTimeMillis() % 1000;
            float pulse = (float) (Math.sin(t / 1000.0 * Math.PI * 2) * 0.2 + 0.2);
            float glowAlpha = pulse * barRatio;
            float ga1 = (float) Math.PI;
            float ga2 = (float) Math.PI + barRatio * (float) Math.PI;
            NVGRenderer.arc(centerX, centerY, RADIUS + 4, ARC_THICKNESS + 8, ga1, ga2, 0xFFFF2020, glowAlpha);
        }

        // === NVG text (if font loaded) ===
        int valColor = cortisol < 0 ? getOverflowColor(overflowRatio) : getStressColor(barRatio);
        int lblColor = cortisol < 0 ? getOverflowColor(overflowRatio)
                : (barRatio > 0.6f ? getStressColor(barRatio) : LABEL_COLOR);

        if (NVGRenderer.hasFont()) {
            NVGRenderer.textCentered(String.format("%.1f", displayCortisol),
                    centerX, centerY + 3, 12, valColor, 1f);
            NVGRenderer.textCentered("CORTISOL", centerX, centerY - RADIUS - 10, 10, lblColor, 1f);
            NVGRenderer.text("0", centerX - RADIUS - 10, centerY - 4, 10, LABEL_DIM, 1f);
            NVGRenderer.text("20", centerX + RADIUS + 3, centerY - 4, 10, LABEL_DIM, 1f);
        }

        NVGRenderer.endFrame();

        // MC text fallback
        if (!NVGRenderer.hasFont()) {
            drawTextMC(ctx, tr, centerX, centerY, displayCortisol, valColor, lblColor);
        }
    }

    // ===================== Legacy fallback (original DrawContext rendering) =====================

    private void renderLegacy(DrawContext ctx, TextRenderer tr, float centerX, float centerY,
                              float barRatio, float overflowRatio, float cortisol, float displayCortisol) {
        int cx = (int) centerX, cy = (int) centerY;

        // Overflow arc
        if (overflowRatio > 0) {
            int overflowSegs = (int) (ARC_SEGMENTS * 0.4f);
            int filledOverflow = (int) (overflowSegs * overflowRatio);
            for (int i = 0; i < filledOverflow; i++) {
                float segStart = (float) i / overflowSegs;
                float segEnd = (float) (i + 1) / overflowSegs;
                float a1 = 0.0f - segEnd * 0.4f;
                float a2 = 0.0f - segStart * 0.4f;
                int color = getOverflowColor(segStart);
                fillArcLegacy(ctx, cx, cy, RADIUS, ARC_THICKNESS, a1, a2, color);
            }
        }

        // Main arc
        for (int i = 0; i < ARC_SEGMENTS; i++) {
            float segStart = (float) i / ARC_SEGMENTS;
            float segEnd = (float) (i + 1) / ARC_SEGMENTS;
            int color = segStart <= barRatio ? getStressColor(segStart) : UNFILLED;
            fillArcLegacy(ctx, cx, cy, RADIUS, ARC_THICKNESS, segStart, segEnd, color);
        }

        // Ticks
        for (int i = 0; i <= 10; i++) {
            float t = (float) i / 10;
            double angle = Math.PI + t * Math.PI;
            int tickInner = RADIUS - ARC_THICKNESS - 2;
            int tickOuter = RADIUS - ARC_THICKNESS - (i % 5 == 0 ? 5 : 3);
            int tx1 = cx + (int) (Math.cos(angle) * tickInner);
            int ty1 = cy + (int) (Math.sin(angle) * tickInner);
            int tx2 = cx + (int) (Math.cos(angle) * tickOuter);
            int ty2 = cy + (int) (Math.sin(angle) * tickOuter);
            ctx.fill(Math.min(tx1, tx2), Math.min(ty1, ty2),
                    Math.max(tx1, tx2) + 1, Math.max(ty1, ty2) + 1, TICK_COLOR);
        }

        // Needle
        float needleRatio = cortisol >= 0 ? barRatio : -overflowRatio * 0.4f;
        double needleAngle = Math.PI + needleRatio * Math.PI;
        int nx = cx + (int) (Math.cos(needleAngle) * NEEDLE_LEN);
        int ny = cy + (int) (Math.sin(needleAngle) * NEEDLE_LEN);

        drawLineLegacy(ctx, cx + 1, cy + 1, nx + 1, ny + 1, NEEDLE_SHADOW);
        int needleCol;
        if (cortisol < 0) needleCol = getOverflowColor(overflowRatio);
        else if (barRatio > 0.7f) needleCol = getStressColor(barRatio);
        else needleCol = NEEDLE_COLOR;
        drawLineLegacy(ctx, cx, cy, nx, ny, needleCol);

        // Center dot
        ctx.fill(cx - 2, cy - 2, cx + 3, cy + 3, CENTER_DOT);
        ctx.fill(cx - 1, cy - 1, cx + 2, cy + 2, 0xFF000000);

        // Glow
        if (barRatio > 0.7f) {
            long t = System.currentTimeMillis() % 1000;
            float pulse = (float) (Math.sin(t / 1000.0 * Math.PI * 2) * 0.2 + 0.2);
            int alpha = (int) (pulse * 180 * barRatio);
            int glow = (Math.min(alpha, 255) << 24) | 0x00FF2020;
            fillArcLegacy(ctx, cx, cy, RADIUS + 4, ARC_THICKNESS + 8, 0, barRatio, glow);
        }

        // Text
        int valColor = cortisol < 0 ? getOverflowColor(overflowRatio) : getStressColor(barRatio);
        int lblColor = cortisol < 0 ? getOverflowColor(overflowRatio)
                : (barRatio > 0.6f ? getStressColor(barRatio) : LABEL_COLOR);
        drawTextMC(ctx, tr, centerX, centerY, displayCortisol, valColor, lblColor);
    }

    private void drawTextMC(DrawContext ctx, TextRenderer tr, float centerX, float centerY,
                            float displayCortisol, int valColor, int lblColor) {
        int cx = (int) centerX, cy = (int) centerY;
        String val = String.format("%.1f", displayCortisol);
        ctx.drawText(tr, val, cx - tr.getWidth(val) / 2, cy + 3, valColor, false);
        ctx.drawText(tr, "0", cx - RADIUS - 10, cy - 4, LABEL_DIM, false);
        ctx.drawText(tr, "20", cx + RADIUS + 3, cy - 4, LABEL_DIM, false);
        String label = "CORTISOL";
        ctx.drawText(tr, label, cx - tr.getWidth(label) / 2, cy - RADIUS - 10, lblColor, false);
    }

    // ===================== Legacy drawing helpers =====================

    private static void fillArcLegacy(DrawContext ctx, int cx, int cy, int radius, int thickness,
                                      float startRatio, float endRatio, int color) {
        int steps = 30;
        for (int i = 0; i < steps; i++) {
            float t1 = startRatio + (endRatio - startRatio) * i / steps;
            float t2 = startRatio + (endRatio - startRatio) * (i + 1) / steps;
            double a1 = Math.PI + t1 * Math.PI;
            double a2 = Math.PI + t2 * Math.PI;
            int ox1 = cx + (int) (Math.cos(a1) * radius);
            int oy1 = cy + (int) (Math.sin(a1) * radius);
            int ox2 = cx + (int) (Math.cos(a2) * radius);
            int oy2 = cy + (int) (Math.sin(a2) * radius);
            int ix1 = cx + (int) (Math.cos(a1) * (radius - thickness));
            int iy1 = cy + (int) (Math.sin(a1) * (radius - thickness));
            int ix2 = cx + (int) (Math.cos(a2) * (radius - thickness));
            int iy2 = cy + (int) (Math.sin(a2) * (radius - thickness));
            int minX = Math.min(Math.min(ox1, ox2), Math.min(ix1, ix2));
            int maxX = Math.max(Math.max(ox1, ox2), Math.max(ix1, ix2));
            int minY = Math.min(Math.min(oy1, oy2), Math.min(iy1, iy2));
            int maxY = Math.max(Math.max(oy1, oy2), Math.max(iy1, iy2));
            if (maxX > minX && maxY > minY) ctx.fill(minX, minY, maxX, maxY, color);
        }
    }

    private static void drawLineLegacy(DrawContext ctx, int x0, int y0, int x1, int y1, int color) {
        int dx = Math.abs(x1 - x0), dy = Math.abs(y1 - y0);
        int sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
        int err = dx - dy;
        while (true) {
            ctx.fill(x0, y0, x0 + 1, y0 + 1, color);
            if (x0 == x1 && y0 == y1) break;
            int e2 = 2 * err;
            if (e2 > -dy) { err -= dy; x0 += sx; }
            if (e2 < dx) { err += dx; y0 += sy; }
        }
    }

    // ===================== Color functions =====================

    private static int getOverflowColor(float t) {
        int r = (int) (20 + 30 * (1 - t));
        int g = (int) (200 + 55 * (1 - t));
        int b = (int) (220 + 35 * (1 - t));
        return 0xFF000000 | (cl(r) << 16) | (cl(g) << 8) | cl(b);
    }

    private static int getStressColor(float stress) {
        int r, g, b;
        if (stress < 0.35f) {
            float t = stress / 0.35f;
            r = (int) (30 + 225 * t); g = (int) (200 + 55 * (1 - t)); b = (int) (40 * (1 - t));
        } else if (stress < 0.65f) {
            float t = (stress - 0.35f) / 0.3f;
            r = 255; g = (int) (230 - 130 * t); b = 0;
        } else {
            float t = (stress - 0.65f) / 0.35f;
            r = 255; g = (int) (100 - 100 * t); b = (int) (30 * t);
        }
        return 0xFF000000 | (cl(r) << 16) | (cl(g) << 8) | cl(b);
    }

    private static int cl(int v) { return Math.max(0, Math.min(255, v)); }
}
