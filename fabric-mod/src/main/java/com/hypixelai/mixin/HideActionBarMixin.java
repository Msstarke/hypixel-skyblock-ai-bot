package com.hypixelai.mixin;

import net.minecraft.client.gui.hud.InGameHud;
import net.minecraft.text.Text;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Hides Hypixel's action bar health/defense/mana overlay.
 * Cancels setOverlayMessage when it contains SkyBlock stat symbols.
 */
@Mixin(InGameHud.class)
public class HideActionBarMixin {

    @Inject(method = "setOverlayMessage", at = @At("HEAD"), cancellable = true)
    private void hideHealthOverlay(Text message, boolean tinted, CallbackInfo ci) {
        String text = message.getString();
        // Hypixel SkyBlock action bar contains these symbols:
        // ❤ (health), ❈ (defense), ✎ (mana), ✦ (overflow mana)
        if (text.contains("\u2764") || text.contains("\u2748") ||
            text.contains("\u270E") || text.contains("\u2726")) {
            ci.cancel();
        }
    }
}
