from homeassistant.core import callback
"""Support for MyHome heating."""

from homeassistant.components.climate import (
    ClimateEntity,
    DOMAIN as PLATFORM,
)
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_MAC,
    UnitOfTemperature,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send

from .ownd.message import (
    OWNHeatingEvent,
    OWNHeatingCommand,
    CLIMATE_MODE_OFF,
    CLIMATE_MODE_HEAT,
    CLIMATE_MODE_COOL,
    CLIMATE_MODE_AUTO,
    MESSAGE_TYPE_MAIN_TEMPERATURE,
    MESSAGE_TYPE_MAIN_HUMIDITY,
    MESSAGE_TYPE_TARGET_TEMPERATURE,
    MESSAGE_TYPE_FAN,
    MESSAGE_TYPE_LOCAL_OFFSET,
    MESSAGE_TYPE_LOCAL_TARGET_TEMPERATURE,
    MESSAGE_TYPE_MODE,
    MESSAGE_TYPE_MODE_TARGET,
    MESSAGE_TYPE_ACTION,
)

from .const import (
    CONF_PLATFORMS,
    CONF_ENTITY,
    CONF_WHO,
    CONF_ZONE,
    CONF_MANUFACTURER,
    CONF_DEVICE_MODEL,
    CONF_HEATING_SUPPORT,
    CONF_COOLING_SUPPORT,
    CONF_FAN_SUPPORT,
    CONF_STANDALONE,
    CONF_CENTRAL,
    DOMAIN,
    LOGGER,
)
from .myhome_device import MyHOMEEntity
from .gateway import MyHOMEGatewayHandler


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the MyHOME light platform dynamically via Discovery."""
    known_climate_zones = set()

    # Restore previously discovered entities from the Entity Registry so they
    # are available immediately on restart, even before the gateway responds.
    entity_registry = er.async_get(hass)
    existing_entries = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    restored_climate_zones = []

    gateway = hass.data[DOMAIN][config_entry.data[CONF_MAC]][CONF_ENTITY]

    for entry in existing_entries:
        if entry.domain == PLATFORM:
            unique_id = entry.unique_id
            # unique_id format: "{mac}-{who}-{device_id}"
            # device_id is "{where}" or "{where}#4#{interface}"
            after_mac = unique_id.replace(f"{config_entry.data[CONF_MAC]}-", "", 1)
            # Strip the WHO prefix: "1-55" -> "55", "1-18#4#02" -> "18#4#02"
            parts_who = after_mac.split("-", 1)
            device_id = parts_who[-1] if len(parts_who) > 1 else after_mac
            if "#4#" in device_id:
                parts = device_id.split("#4#")
                where = parts[0]
                interface = parts[1] if len(parts) > 1 else None
            else:
                where = device_id
                interface = None

            _customs = hass.data.get(DOMAIN, {}).get("customizations", {})
            clean_where = where.split('-')[-1]
            _predicted_id = f"climate.climate_{clean_where.replace(' ', '_')}"
            _custom = _customs.get(_predicted_id, {})
            
            _is_standalone = _custom.get("standalone", True)
            _is_central = _custom.get("central", False)
            _is_heating = _custom.get("heating", True)
            _is_cooling = _custom.get("cooling", True)
            _is_fan = _custom.get("fan", False)
            
            _model = _custom.get("model", "Climate Device")
            _name = _custom.get("friendly_name", f"Climate Zone {clean_where}")

            _climate_zone = MyHOMEClimate(
                hass=hass,
                name=_name,
                device_id=device_id,
                who="4",
                where=where,
                heating=_is_heating,
                cooling=_is_cooling,
                fan=_is_fan,
                standalone=_is_standalone,
                central=_is_central,
                manufacturer="BTicino",
                model=_model,
                gateway=gateway,
            )
            known_climate_zones.add(device_id)
            restored_climate_zones.append(_climate_zone)

    if restored_climate_zones:
        async_add_entities(restored_climate_zones)

    @callback
    def async_add_climate_zone(message):
        """Add a climate zone from a discovered message."""
        if not hasattr(message, "where") or not message.where or message.where == "0" or message.where == "#0":
            return

        # Skip groups, areas and general for now, as they represent many physical devices
        if getattr(message, "is_group", False) or getattr(message, "is_area", False) or getattr(message, "is_general", False):
            return

        where = message.where
        interface = getattr(message, "interface", None)
        unique_id = f"{where}#4#{interface}" if interface else str(where)

        if unique_id not in known_climate_zones:
            # We found a new climate zone!
            clean_where = where.split('-')[-1]
        
            _customs = hass.data.get(DOMAIN, {}).get("customizations", {})
            _predicted_id = f"climate.climate_{clean_where.replace(' ', '_')}"
            _custom = _customs.get(_predicted_id, {})
        
            _is_standalone = _custom.get("standalone", True)
            _is_central = _custom.get("central", False)
            _is_heating = _custom.get("heating", True)
            _is_cooling = _custom.get("cooling", True)
            _is_fan = _custom.get("fan", False)
        
            _model = _custom.get("model", "Climate Device")
            _name = _custom.get("friendly_name", f"Climate Zone {clean_where}")
        
            _climate_zone = MyHOMEClimate(
                hass=hass,
                name=_name,
                device_id=unique_id,
                who=str(message.who),
                where=where,
                heating=_is_heating,
                cooling=_is_cooling,
                fan=_is_fan,
                standalone=_is_standalone,
                central=_is_central,
                manufacturer="BTicino",
                model=_model,
                gateway=hass.data[DOMAIN][config_entry.data[CONF_MAC]][CONF_ENTITY],
            )
            known_climate_zones.add(unique_id)
            async_add_entities([_climate_zone])
            _climate_zone.handle_event(message)

        async_dispatcher_send(hass, f"myhome_update_{config_entry.data[CONF_MAC]}_4_{unique_id}", message)

    @callback
    def _handle_climate_zone_message(msg):
        """Filter and forward Climate messages."""
        if isinstance(msg, OWNHeatingEvent):
            async_add_climate_zone(msg)
            
    # Listen to all incoming gateway messages
    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"myhome_message_{config_entry.data[CONF_MAC]}",
            _handle_climate_zone_message,
        )
    )

async def async_unload_entry(hass, config_entry):
    """Unload light platform."""
    return True

    for _climate_device in list(_configured_climate_devices.keys()):
        del hass.data[DOMAIN][config_entry.data[CONF_MAC]][CONF_PLATFORMS][PLATFORM][
            _climate_device
        ]


class MyHOMEClimate(MyHOMEEntity, ClimateEntity):
    def __init__(
        self,
        hass,
        name: str,
        device_id: str,
        who: str,
        where: str,
        heating: bool,
        cooling: bool,
        fan: bool,
        standalone: bool,
        central: bool,
        manufacturer: str,
        model: str,
        gateway: MyHOMEGatewayHandler,
    ):
        super().__init__(
            hass=hass,
            name=name,
            platform=PLATFORM,
            device_id=device_id,
            who=who,
            where=where,
            manufacturer=manufacturer,
            model=model,
            gateway=gateway,
        )

        self._standalone = standalone
        self._central = True if self._where == "#0" else central

        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_precision = 0.1
        self._attr_target_temperature_step = 0.5
        self._attr_min_temp = 5
        self._attr_max_temp = 40

        self._attr_supported_features = 0
        self._attr_hvac_modes = [HVACMode.OFF]
        self._heating = heating
        self._cooling = cooling
        if heating or cooling:
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
            #if not self._central:
            #    self._attr_hvac_modes.append(HVACMode.AUTO)
            if heating:
                self._attr_hvac_modes.append(HVACMode.HEAT)
            if cooling:
                self._attr_hvac_modes.append(HVACMode.COOL)

        # Fan mode is not yet implemented in the OpenWebNet protocol handler.
        # Do not advertise FAN_MODE to avoid NotImplementedError in the UI.
        self._fan = fan
        
        if fan:
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
            self._attr_fan_modes = ["auto", "low", "medium", "high"]
            self._attr_fan_mode = None

        self._attr_current_temperature = None
        self._attr_current_humidity = None
        self._target_temperature = None
        self._local_offset = 0
        self._local_target_temperature = None

        self._attr_hvac_mode = None
        self._attr_hvac_action = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await self._gateway_handler.send(OWNHeatingCommand.status(self._where))
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"myhome_update_{self._gateway_handler.mac}_4_{self._where}",
                self.handle_event,
            )
        )

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._gateway_handler.send_status_request(
            OWNHeatingCommand.status(self._where)
        )

    @property
    def fan_mode(self):
        return getattr(self, "_attr_fan_mode", None)
    
    @property
    def fan_modes(self):
        return ["auto", "low", "medium", "high"]

    @property
    def target_temperature(self) -> float:
        if self._local_target_temperature is not None:
            return self._local_target_temperature
        else:
            return self._target_temperature


    # in OWN fan (dimension 11) is read-only
    async def async_set_fan_mode(self, fan_mode):
        """Set fan mode."""
        LOGGER.debug(
            "Fan mode change requested but not supported: %s",
            fan_mode,
        )
    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self._gateway_handler.send(
                OWNHeatingCommand.set_mode(
                    where=self._where,
                    mode=CLIMATE_MODE_OFF,
                    standalone=self._standalone,
                )
            )
        #elif hvac_mode == HVACMode.AUTO:
        #    await self._gateway_handler.send(
        #        OWNHeatingCommand.set_mode(
        #            where=self._where,
        #            mode=CLIMATE_MODE_AUTO,
        #            standalone=self._standalone,
        #        )
        #    )
        elif hvac_mode == HVACMode.HEAT:
            if self._target_temperature is not None:
                await self._gateway_handler.send(
                    OWNHeatingCommand.set_temperature(
                        where=self._where,
                        temperature=self._target_temperature,
                        mode=CLIMATE_MODE_HEAT,
                        standalone=self._standalone,
                    )
                )
        elif hvac_mode == HVACMode.COOL:
            if self._target_temperature is not None:
                await self._gateway_handler.send(
                    OWNHeatingCommand.set_temperature(
                        where=self._where,
                        temperature=self._target_temperature,
                        mode=CLIMATE_MODE_COOL,
                        standalone=self._standalone,
                    )
                )


    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temperature = (
            kwargs.get("temperature", self._local_target_temperature)
            - self._local_offset
        )
        if self._attr_hvac_mode == HVACMode.HEAT:
            await self._gateway_handler.send(
                OWNHeatingCommand.set_temperature(
                    where=self._where,
                    temperature=target_temperature,
                    mode=CLIMATE_MODE_HEAT,
                    standalone=self._standalone,
                )
            )
        elif self._attr_hvac_mode == HVACMode.COOL:
            await self._gateway_handler.send(
                OWNHeatingCommand.set_temperature(
                    where=self._where,
                    temperature=target_temperature,
                    mode=CLIMATE_MODE_COOL,
                    standalone=self._standalone,
                )
            )
        #else:
        #    await self._gateway_handler.send(
        #        OWNHeatingCommand.set_temperature(
        #            where=self._where,
        #            temperature=target_temperature,
        #            mode=CLIMATE_MODE_AUTO,
        #            standalone=self._standalone,
        #        )
        #    )

    @callback
    def handle_event(self, message: OWNHeatingEvent):
        """Handle an event message."""
        if message.message_type == MESSAGE_TYPE_MAIN_TEMPERATURE:
            LOGGER.info(
                "%s %s",
                self._gateway_handler.log_id,
                message.human_readable_log,
            )
            self._attr_current_temperature = message.main_temperature
        elif message.message_type == MESSAGE_TYPE_MAIN_HUMIDITY:
            LOGGER.info(
                "%s %s",
                self._gateway_handler.log_id,
                message.human_readable_log,
            )
            self._attr_current_humidity = message.main_humidity
        elif message.message_type == MESSAGE_TYPE_TARGET_TEMPERATURE:
            LOGGER.info(
                "%s %s",
                self._gateway_handler.log_id,
                message.human_readable_log,
            )
            self._target_temperature = message.set_temperature
            self._local_target_temperature = (
                self._target_temperature + self._local_offset
            )
        # -------------------- FAN
        elif message.message_type == MESSAGE_TYPE_FAN and self._fan:
            LOGGER.info(
                "%s %s",
                self._gateway_handler.log_id,
                message.human_readable_log,
            )
            fan_map = {
                0: "auto",
                1: "low",
                2: "medium",
                3: "high",
            }
        
            self._attr_fan_mode = fan_map.get(message._fan_speed)
        # ------------------------------------ FAN END
        elif message.message_type == MESSAGE_TYPE_LOCAL_OFFSET:
            LOGGER.info(
                "%s %s",
                self._gateway_handler.log_id,
                message.human_readable_log,
            )
            self._local_offset = message.local_offset
            if self._target_temperature is not None:
                self._local_target_temperature = (
                    self._target_temperature + self._local_offset
                )
        elif message.message_type == MESSAGE_TYPE_LOCAL_TARGET_TEMPERATURE:
            LOGGER.info(
                "%s %s",
                self._gateway_handler.log_id,
                message.human_readable_log,
            )
            self._local_target_temperature = message.local_set_temperature
            self._target_temperature = (
                self._local_target_temperature - self._local_offset
            )
        elif message.message_type == MESSAGE_TYPE_MODE:
            #if (
            #    message.mode == CLIMATE_MODE_AUTO
            #    and HVACMode.AUTO in self._attr_hvac_modes
            #):
            #    LOGGER.info(
            #        "%s %s",
            #        self._gateway_handler.log_id,
            #        message.human_readable_log,
            #    )
            #    self._attr_hvac_mode = HVACMode.AUTO
            #    if self._attr_hvac_action == HVACAction.OFF:
            #        self._attr_hvac_action = HVACAction.IDLE
            if (
                message.mode == CLIMATE_MODE_COOL
                and HVACMode.COOL in self._attr_hvac_modes
            ):
                LOGGER.info(
                    "%s %s",
                    self._gateway_handler.log_id,
                    message.human_readable_log,
                )
                self._attr_hvac_mode = HVACMode.COOL
                if self._attr_hvac_action == HVACAction.OFF:
                    self._attr_hvac_action = HVACAction.IDLE
            elif (
                message.mode == CLIMATE_MODE_HEAT
                and HVACMode.HEAT in self._attr_hvac_modes
            ):
                LOGGER.info(
                    "%s %s",
                    self._gateway_handler.log_id,
                    message.human_readable_log,
                )
                self._attr_hvac_mode = HVACMode.HEAT
                if self._attr_hvac_action == HVACAction.OFF:
                    self._attr_hvac_action = HVACAction.IDLE
            elif message.mode == CLIMATE_MODE_OFF:
                LOGGER.info(
                    "%s %s",
                    self._gateway_handler.log_id,
                    message.human_readable_log,
                )
                self._attr_hvac_mode = HVACMode.OFF
                self._attr_hvac_action = HVACAction.OFF
        elif message.message_type == MESSAGE_TYPE_MODE_TARGET:
            #if (
            #    message.mode == CLIMATE_MODE_AUTO
            #    and HVACMode.AUTO in self._attr_hvac_modes
            #):
            #    LOGGER.info(
            #        "%s %s",
            #        self._gateway_handler.log_id,
            #        message.human_readable_log,
            #    )
            #    self._attr_hvac_mode = HVACMode.AUTO
            #    if self._attr_hvac_action == HVACAction.OFF:
            #        self._attr_hvac_action = HVACAction.IDLE
            if (
                message.mode == CLIMATE_MODE_COOL
                and HVACMode.COOL in self._attr_hvac_modes
            ):
                LOGGER.info(
                    "%s %s",
                    self._gateway_handler.log_id,
                    message.human_readable_log,
                )
                self._attr_hvac_mode = HVACMode.COOL
                if self._attr_hvac_action == HVACAction.OFF:
                    self._attr_hvac_action = HVACAction.IDLE
            elif (
                message.mode == CLIMATE_MODE_HEAT
                and HVACMode.HEAT in self._attr_hvac_modes
            ):
                LOGGER.info(
                    "%s %s",
                    self._gateway_handler.log_id,
                    message.human_readable_log,
                )
                self._attr_hvac_mode = HVACMode.HEAT
                if self._attr_hvac_action == HVACAction.OFF:
                    self._attr_hvac_action = HVACAction.IDLE
            elif message.mode == CLIMATE_MODE_OFF:
                LOGGER.info(
                    "%s %s",
                    self._gateway_handler.log_id,
                    message.human_readable_log,
                )
                self._attr_hvac_mode = HVACMode.OFF
                self._attr_hvac_action = HVACAction.OFF
            self._target_temperature = message.set_temperature
            self._local_target_temperature = (
                self._target_temperature + self._local_offset
            )
        elif message.message_type == MESSAGE_TYPE_ACTION:
            LOGGER.info(
                "%s %s",
                self._gateway_handler.log_id,
                message.human_readable_log,
            )
            if message.is_active():
                if self._heating and self._cooling:
                    if message.is_heating():
                        self._attr_hvac_action = HVACAction.HEATING
                    elif message.is_cooling():
                        self._attr_hvac_action = HVACAction.COOLING
                elif self._heating:
                    self._attr_hvac_action = HVACAction.HEATING
                elif self._cooling:
                    self._attr_hvac_action = HVACAction.COOLING
            elif self._attr_hvac_mode == HVACMode.OFF:
                self._attr_hvac_action = HVACAction.OFF
            else:
                self._attr_hvac_action = HVACAction.IDLE

        self.async_schedule_update_ha_state()
