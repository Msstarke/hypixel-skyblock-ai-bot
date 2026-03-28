package com.hypixelai.mixin;

import com.hypixelai.HypixelAIConfig;
import net.minecraft.client.gui.hud.InGameHud;
import net.minecraft.text.Text;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(InGameHud.class)
public class HideActionBarMixin {
    @Inject(method = "setOverlayMessage", at = @At("HEAD"), cancellable = true)
    private void hideHealthOverlay(Text message, boolean tinted, CallbackInfo ci) {
        if (!HypixelAIConfig.isHideActionBar()) return;
        String text = message.getString();
        if (text.contains("\u2764") || text.contains("\u2748") ||
            text.contains("\u270E") || text.contains("\u2726")) {
            ci.cancel();
        }
    }
}
