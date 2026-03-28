package com.hypixelai.mixin;

import net.minecraft.client.gui.hud.InGameHud;
import net.minecraft.client.gui.DrawContext;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Mixin to cancel vanilla heart rendering.
 * The cortisol bar replaces hearts entirely.
 */
@Mixin(InGameHud.class)
public class HideHeartsMixin {

    @Inject(method = "renderHealthBar", at = @At("HEAD"), cancellable = true)
    private void hideHealthBar(CallbackInfo ci) {
        ci.cancel();
    }
}
