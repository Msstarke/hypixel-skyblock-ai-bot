package com.hypixelai;

import net.fabricmc.api.ModInitializer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class HypixelAIMod implements ModInitializer {
    public static final String MOD_ID = "hypixelai";
    public static final Logger LOGGER = LoggerFactory.getLogger(MOD_ID);

    @Override
    public void onInitialize() {
        LOGGER.info("[HypixelAI] Mod initialized. Use !ai <question> in chat.");
    }
}
