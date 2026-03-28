package com.hypixelai.mixin;

import com.hypixelai.HypixelAIConfig;
import net.minecraft.client.gui.hud.InGameHud;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(InGameHud.class)
public class HideHeartsMixin {
    @Inject(method = "renderHealthBar", at = @At("HEAD"), cancellable = true)
    private void hideHealthBar(CallbackInfo ci) {
        if (HypixelAIConfig.isHideHearts()) {
            ci.cancel();
        }
    }
}
