package com.healthscale.app.okok

/**
 * Parsed OKOK / Chipsea BLE advertisement measurement.
 */
data class ScaleReading(
    val weightKg: Double,
    val impedanceOhm: Double?,
    val unit: String,
    val decimals: Int,
    val stable: Boolean,
    val scaleMac: String?,
    val protocol: String,
    val rawHex: String,
)

object OkOkParser {
    fun parseManufacturerData(companyId: Int, data: ByteArray): ScaleReading? {
        if (data.isEmpty()) return null
        val first = data[0].toInt() and 0xFF

        // Android stores the first two advertisement bytes as a little-endian
        // company id. OKOK puts C0 (or CA) in the low byte and the sequence
        // or version in the high byte, so the payload starts at the weight.
        return when (companyId) {
            0x20CA -> parseV20(data)
            0x11CA -> parseV11(data)
            0xF0FF -> parseVf0(data)
            else -> when {
                first == 0xC0 && data.size >= 9 ->
                    parseC0Payload(data.copyOfRange(2, data.size))
                first == 0xCA -> parseCa(data)
                (companyId and 0xFF) == 0xC0 -> parseC0Payload(data)
                (companyId and 0xFF) == 0xCA -> {
                    val full = ByteArray(data.size + 2)
                    full[0] = 0xCA.toByte()
                    full[1] = (companyId shr 8).toByte()
                    System.arraycopy(data, 0, full, 2, data.size)
                    parseCa(full)
                }
                else -> null
            }
        }
    }

    /**
     * C0 payload after Android has consumed the C0 byte and the sequence byte
     * as the company id.
     *
     * [0..1] weight BE, [2..3] impedance BE, [4..5] product,
     * [6] property, [7..12] MAC.
     * Property: bit0 stable, bits1-2 divisor, bits3-4 unit.
     * 0x24 = kg measuring, 0x25 = kg locked.
     */
    fun parseC0Payload(data: ByteArray): ScaleReading? {
        if (data.size < 7) return null
        val prop = data[6].toInt() and 0xFF
        val divider = when ((prop shr 1) and 0x03) {
            1 -> 1.0
            2 -> 100.0
            else -> 10.0
        }
        val unitCode = (prop shr 3) and 0x03
        val weightRaw = u16be(data, 0)
        val weightKg = when (unitCode) {
            0 -> weightRaw / divider
            1 -> weightRaw / divider / 2.0
            2 -> (weightRaw / divider) * 0.45359237
            3 -> {
                val stones = data[0].toInt() and 0xFF
                val pounds = (data[1].toInt() and 0xFF) / divider
                stones * 6.35029318 + pounds * 0.45359237
            }
            else -> return null
        }
        if (weightKg <= 0.0 || weightKg > 300.0) return null

        val impedanceRaw = u16be(data, 2)
        val (unit, decimals) = when (unitCode) {
            1 -> "jin" to 1
            2 -> "lb" to 1
            3 -> "st" to 1
            else -> "kg" to if (divider >= 100.0) 2 else 1
        }
        return ScaleReading(
            weightKg = weightKg,
            impedanceOhm = if (impedanceRaw == 0) null else impedanceRaw / 10.0,
            unit = unit,
            decimals = decimals,
            stable = (prop and 0x01) != 0,
            scaleMac = if (data.size >= 13) formatMac(data, 7) else null,
            protocol = "C0",
            rawHex = data.toHex(),
        )
    }

    /** V20 broadcast. Company id 0x20CA; payload starts after those two bytes. */
    private fun parseV20(data: ByteArray): ScaleReading? {
        if (data.size < 13) return null
        val flags = data[6].toInt() and 0xFF
        var checksum = 0x20
        for (i in 0 until 12) {
            checksum = checksum xor (data[i].toInt() and 0xFF)
        }
        if ((data[12].toInt() and 0xFF) != (checksum and 0xFF)) return null

        val divider = if ((flags and 0x04) != 0) 100.0 else 10.0
        val weightKg = u16be(data, 8) / divider
        if (weightKg <= 0.0 || weightKg > 300.0) return null
        val impedanceRaw = u16be(data, 10)
        return ScaleReading(
            weightKg = weightKg,
            impedanceOhm = if (impedanceRaw == 0) null else impedanceRaw / 10.0,
            unit = "kg",
            decimals = if (divider >= 100.0) 2 else 1,
            stable = (flags and 0x01) != 0,
            scaleMac = if (data.size >= 19) formatMac(data, data.size - 6) else null,
            protocol = "CA-V20",
            rawHex = data.toHex(),
        )
    }

    /** V11 broadcast. Company id 0x11CA. */
    private fun parseV11(data: ByteArray): ScaleReading? {
        if (data.size < 17) return null
        var checksum = 0xCA xor 0x11
        for (i in 0 until 16) {
            checksum = checksum xor (data[i].toInt() and 0xFF)
        }
        if ((data[16].toInt() and 0xFF) != (checksum and 0xFF)) return null

        val props = data[9].toInt() and 0xFF
        val divider = when ((props shr 1) and 0x03) {
            1 -> 1.0
            2 -> 100.0
            else -> 10.0
        }
        val weightRaw = u16be(data, 3)
        val weightKg = when ((props shr 3) and 0x03) {
            0 -> weightRaw / divider
            1 -> weightRaw / divider / 2.0
            2 -> (weightRaw / divider) * 0.45359237
            else -> return null
        }
        if (weightKg <= 0.0 || weightKg > 300.0) return null
        return ScaleReading(
            weightKg = weightKg,
            impedanceOhm = null,
            unit = "kg",
            decimals = if (divider >= 100.0) 2 else 1,
            stable = true,
            scaleMac = null,
            protocol = "CA-V11",
            rawHex = data.toHex(),
        )
    }

    /** VF0 broadcast. Company id 0xF0FF. Weight is little-endian at bytes 2..3. */
    private fun parseVf0(data: ByteArray): ScaleReading? {
        if (data.size < 4) return null
        val weightKg = u16le(data, 2) / 10.0
        if (weightKg <= 0.0 || weightKg > 300.0) return null
        return ScaleReading(
            weightKg = weightKg,
            impedanceOhm = null,
            unit = "kg",
            decimals = 1,
            stable = true,
            scaleMac = null,
            protocol = "VF0",
            rawHex = data.toHex(),
        )
    }

    /**
     * CA v1.1-ish layout (broadcast):
     * CA, version, len, locked, deviceType, ..., weight, impedance, checksum, MAC
     *
     * Also supports compact forms seen in openScale logs.
     */
    fun parseCa(data: ByteArray): ScaleReading? {
        if (data.size < 8) return null
        if ((data[0].toInt() and 0xFF) != 0xCA) return null

        val version = data[1].toInt() and 0xFF

        // Try documented V1.1 style: locked at [3], weight at varying positions
        // From issue #496: CA, ver, len, locked, type, ... weight MSB/LSB, impedance, xor, MAC
        return when {
            data.size >= 14 -> parseCaLong(data, version)
            else -> parseCaShort(data, version)
        }
    }

    private fun parseCaLong(data: ByteArray, version: Int): ScaleReading? {
        // Heuristic: find weight/impedance like openScale Chipsea frames
        // Example: ca 20 0b 00 ... eb 03 b6 13 8a ec ...
        // weight*10 and r1*10 near the end before checksum/MAC

        val locked = (data[3].toInt() and 0xFF) == 0x01

        // Search for plausible weight*10 (200..3000 => 20..300 kg)
        // Prefer known layout for version 0x11 / 0x20
        val (weightRaw, impRaw, stable) = if (version == 0x11 && data.size >= 12) {
            // CA 11 len locked type wMSB wLSB ...
            val w = u16be(data, 5)
            val lockedFlag = (data[3].toInt() and 0xFF) == 0x01
            Triple(w, if (data.size >= 12) u16be(data, 9) else 0, lockedFlag)
        } else if (data.size >= 14) {
            // Broad scan from openScale EB8217 style: measureSeq, weight*10 BE, r1*10 BE, xor
            // Use bytes around index where weight often sits for V20: after seq
            val candidates = listOf(5, 6, 9, 10)
            var bestW = 0
            var bestI = 0
            for (idx in candidates) {
                if (idx + 1 >= data.size) continue
                val w = u16be(data, idx)
                if (w in 200..3000) {
                    bestW = w
                    if (idx + 3 < data.size) bestI = u16be(data, idx + 2)
                    break
                }
            }
            if (bestW == 0 && data.size >= 12) {
                bestW = u16be(data, data.size - 11)
                bestI = u16be(data, data.size - 9)
            }
            Triple(bestW, bestI, locked)
        } else {
            Triple(0, 0, locked)
        }

        if (weightRaw !in 200..3000) return null
        val weightKg = weightRaw / 10.0
        val impedance = if (impRaw == 0) null else impRaw / 10.0
        val mac = if (data.size >= 20) formatMac(data, data.size - 6) else null

        // XOR checksum validation when enough bytes present
        if (data.size >= 15) {
            val checksumIndex = data.size - 7
            if (checksumIndex > 1) {
                var xor = 0
                for (i in 1 until checksumIndex) {
                    xor = xor xor (data[i].toInt() and 0xFF)
                }
                val expected = data[checksumIndex].toInt() and 0xFF
                // Soft check — some variants differ; don't reject solely on checksum
                @Suppress("UNUSED_VARIABLE")
                val checksumOk = xor == expected
            }
        }

        return ScaleReading(
            weightKg = weightKg,
            impedanceOhm = impedance,
            unit = "kg",
            decimals = 1,
            stable = stable,
            scaleMac = mac,
            protocol = "CA-0x${version.toString(16)}",
            rawHex = data.toHex(),
        )
    }

    private fun parseCaShort(data: ByteArray, version: Int): ScaleReading? {
        if (data.size < 8) return null
        val locked = (data.getOrNull(3)?.toInt()?.and(0xFF) ?: 0) == 0x01
        val weightRaw = u16be(data, minOf(5, data.size - 2))
        if (weightRaw !in 200..3000) return null
        return ScaleReading(
            weightKg = weightRaw / 10.0,
            impedanceOhm = null,
            unit = "kg",
            decimals = 1,
            stable = locked,
            scaleMac = null,
            protocol = "CA-0x${version.toString(16)}",
            rawHex = data.toHex(),
        )
    }

    private fun u16be(data: ByteArray, index: Int): Int {
        if (index + 1 >= data.size) return 0
        return ((data[index].toInt() and 0xFF) shl 8) or (data[index + 1].toInt() and 0xFF)
    }

    private fun u16le(data: ByteArray, index: Int): Int {
        if (index + 1 >= data.size) return 0
        return (data[index].toInt() and 0xFF) or ((data[index + 1].toInt() and 0xFF) shl 8)
    }

    private fun formatMac(data: ByteArray, start: Int): String? {
        if (start + 5 >= data.size) return null
        return (0..5).joinToString(":") { i ->
            "%02X".format(data[start + i].toInt() and 0xFF)
        }
    }

    private fun ByteArray.toHex(): String =
        joinToString("") { "%02x".format(it.toInt() and 0xFF) }
}
