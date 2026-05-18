"""Quick test: switch Bureau (Amp 21) between Radio and Aux via Standard CEN.

This script sends WHO=15 virtual button presses to the MH200 gateway,
triggering the native scenarios programmed in TiMH200.

Usage:
    python mcp_server/test_bureau_source.py

Prerequisites:
    - MH200 must have the RADIOBUREAU (Drukknop 1) and AUXBUREAU (Drukknop 2)
      scenarios programmed on Commando 21.
    - Gateway reachable at 192.168.1.40:20000.
"""

import asyncio
import sys


GATEWAY_IP = "192.168.1.40"
GATEWAY_PORT = 20000
PASSWORD = "12345"

# CEN Trigger strings for Bureau (Commando address = 21)
# Standard CEN syntax: *15*<ButtonNumber>*<CommandoAddress>##
RADIO_BUREAU = "*15*1*21##"   # Drukknop 1 = Radio
AUX_BUREAU   = "*15*2*21##"   # Drukknop 2 = Aux/Cambridge


# ── OPEN password algorithm (from ownd/connection.py) ────────────────────────

def _get_own_password(password: str, nonce: str) -> int:
    """Compute the OPEN protocol password hash from a numeric nonce."""
    start = True
    num1 = 0
    num2 = 0
    password_int = int(password)
    for character in nonce:
        if character != "0":
            if start:
                num2 = password_int
            start = False
        if character == "1":
            num1 = (num2 & 0xFFFFFF80) >> 7
            num2 = num2 << 25
        elif character == "2":
            num1 = (num2 & 0xFFFFFFF0) >> 4
            num2 = num2 << 28
        elif character == "3":
            num1 = (num2 & 0xFFFFFFF8) >> 3
            num2 = num2 << 29
        elif character == "4":
            num1 = num2 << 1
            num2 = num2 >> 31
        elif character == "5":
            num1 = num2 << 5
            num2 = num2 >> 27
        elif character == "6":
            num1 = num2 << 12
            num2 = num2 >> 20
        elif character == "7":
            num1 = (
                num2 & 0x0000FF00
                | ((num2 & 0x000000FF) << 24)
                | ((num2 & 0x00FF0000) >> 16)
            )
            num2 = (num2 & 0xFF000000) >> 8
        elif character == "8":
            num1 = (num2 & 0x0000FFFF) << 16 | (num2 >> 24)
            num2 = (num2 & 0x00FF0000) >> 8
        elif character == "9":
            num1 = ~num2
        else:
            num1 = num2

        num1 &= 0xFFFFFFFF
        num2 &= 0xFFFFFFFF
        if character not in "09":
            num1 |= num2
        num2 = num1
    return num1


async def open_command_session():
    """Open a raw OpenWebNet COMMAND session with proper OPEN auth."""
    reader, writer = await asyncio.open_connection(GATEWAY_IP, GATEWAY_PORT)

    # Read the ACK greeting
    greeting = await asyncio.wait_for(reader.readuntil(b"##"), timeout=5)
    print(f"  Gateway says: {greeting.decode().strip()}")

    # Request a COMMAND session
    writer.write(b"*99*0##")
    await writer.drain()

    # Read the nonce challenge
    resp = await asyncio.wait_for(reader.readuntil(b"##"), timeout=5)
    resp_str = resp.decode().strip()
    print(f"  Challenge: {resp_str}")

    if resp_str == "*#*1##":
        print("  No authentication required — session open!")
        return reader, writer

    # Extract the nonce from *#NONCE##
    nonce = resp_str.replace("*#", "").replace("##", "")
    hashed = _get_own_password(PASSWORD, nonce)
    auth_msg = f"*#{hashed}##"
    print(f"  Sending hashed password...")

    writer.write(auth_msg.encode())
    await writer.drain()

    ack = await asyncio.wait_for(reader.readuntil(b"##"), timeout=5)
    ack_str = ack.decode().strip()
    if "*#*1" in ack_str:
        print("  Authentication successful! [OK]")
    else:
        print(f"  Authentication FAILED: {ack_str}")
        writer.close()
        sys.exit(1)

    return reader, writer


async def send_command(writer, reader, command_str: str):
    """Send a raw OWN command and read the ACK/NACK."""
    print(f"\n  >> Sending: {command_str}")
    writer.write(command_str.encode("ascii"))
    await writer.drain()

    try:
        resp = await asyncio.wait_for(reader.readuntil(b"##"), timeout=3)
        resp_str = resp.decode().strip()
        if "*#*1" in resp_str:
            print(f"  << ACK [OK]  (command accepted)")
        elif "*#*0" in resp_str:
            print(f"  << NACK [FAIL] (command rejected by gateway)")
        else:
            print(f"  << Response: {resp_str}")
    except asyncio.TimeoutError:
        print("  << No response (timeout — command may still have executed)")


async def main():
    print("=" * 60)
    print("  Bureau Source Switch Test (Standard CEN / WHO=15)")
    print("=" * 60)

    print(f"\n[1] Connecting to MH200 at {GATEWAY_IP}:{GATEWAY_PORT}...")
    try:
        reader, writer = await open_command_session()
    except Exception as e:
        print(f"  FAILED to connect: {e}")
        sys.exit(1)

    print("\n[2] Switching Bureau to RADIO (Drukknop 1)...")
    await send_command(writer, reader, RADIO_BUREAU)

    print("\n>>> Listen for 8 seconds — is the Radio playing? Any hiss?")
    await asyncio.sleep(8)

    print("\n[3] Switching Bureau to AUX (Drukknop 2)...")
    await send_command(writer, reader, AUX_BUREAU)

    print("\n>>> Listen for 8 seconds — is the Cambridge/Aux playing? Any hiss?")
    await asyncio.sleep(8)

    print("\n[4] Switching back to RADIO...")
    await send_command(writer, reader, RADIO_BUREAU)

    print("\n>>> Final 5 second listen...")
    await asyncio.sleep(5)

    # Clean up
    print("\n[5] Closing connection...")
    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass

    print("\n" + "=" * 60)
    print("  TEST COMPLETE")
    print("  If all switches were silent (no hiss/pop), the CEN")
    print("  macros on the MH200 are working perfectly!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
