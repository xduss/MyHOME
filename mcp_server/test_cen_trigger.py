import asyncio
import sys
import os

# Add custom_components to path so we can use the existing GatewayClient
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "custom_components", "myhome"))

from own_client import GatewayClient

async def test_native_cen_macro(c, source_num, zone_where):
    """Fires the Standard CEN (WHO=15) trigger to execute the MH200 macro."""
    
    # Syntax: *15*<ButtonNumber>#<Action>*<CommandoAddress>##
    # Action 00 = Short Press
    command_str = f"*15*{source_num}#00*{zone_where}##"
    
    print(f"\n[+] Triggering Native Scenario for Source {source_num} on Amp {zone_where}")
    print(f"    Sending CEN String: {command_str}")
    
    await c.send_raw(command_str)

async def main():
    print("=== MH200 Native Scenario Verification ===")
    
    # Connect to the F454 / MH200 Gateway
    # Note: Password "12345" is usually for the OPEN OpenWebNet password, not the Ethernet config.
    c = GatewayClient("192.168.1.40", password="12345")
    await c.connect()
    
    try:
        # Trigger Drukknop 1 (Radio) on Commando 21
        await test_native_cen_macro(c, source_num=1, zone_where="21")
        
        print("\n>>> Listen! Do you hear the Radio? Is it switching hiss-free? (Waiting 8 sec)")
        await asyncio.sleep(8)
        
        # Trigger Drukknop 2 (Cambridge) on Commando 21
        await test_native_cen_macro(c, source_num=2, zone_where="21")
        
        print("\n>>> Listen! Do you hear Cambridge? Is it switching hiss-free? (Waiting 8 sec)")
        await asyncio.sleep(8)
        
    finally:
        print("\n=== Turning OFF Audio and Disconnecting ===")
        # Standard OFF command for the amplifier
        await c.send_raw("*16*0*21##")
        await c.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
