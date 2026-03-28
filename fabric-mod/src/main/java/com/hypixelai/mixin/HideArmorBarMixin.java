package com.hypixelai.mixin;

import net.minecraft.client.gui.hud.InGameHud;
import net.minecraft.client.gui.DrawContext;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Hides the vanilla armor bar. Cortisol gauge replaces it.
 */
@Mixin(InGameHud.class)
public class HideArmorBarMixin {

    @Inject(method = "renderArmor", at = @At("HEAD"), cancellable = true)
    private static void hideArmorBar(DrawContext context, int i, int j, int k, int l, CallbackInfo ci) {
        ci.cancel();
    }
}
