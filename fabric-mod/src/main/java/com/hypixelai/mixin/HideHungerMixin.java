package com.hypixelai.mixin;

import com.hypixelai.HypixelAIConfig;
import net.minecraft.client.gui.hud.InGameHud;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.entity.player.PlayerEntity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(InGameHud.class)
public class HideHungerMixin {
    @Inject(method = "renderFood", at = @At("HEAD"), cancellable = true)
    private void hideFood(DrawContext context, PlayerEntity player, int top, int right, CallbackInfo ci) {
        if (HypixelAIConfig.isHideHearts()) {
            ci.cancel();
        }
    }
}
