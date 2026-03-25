// SensorDump — thin wrapper around LibreHardwareMonitor that outputs all sensor
// readings as a JSON array on stdout.  Designed to be called as a subprocess by
// the Touchstone Python app so Python does not need a .NET binding.
//
// Output format (one JSON array, minified):
//   [
//     {
//       "hardware": "Intel Core i9-13900H",
//       "parent": null,               // null for top-level hardware
//       "type": "Temperature",        // LHM SensorType enum name
//       "name": "CPU Package",
//       "value": 52.0                 // null if sensor has no current reading
//     },
//     ...
//   ]
//
// Exit codes:  0 = success, 1 = error (message on stderr).
// Requires Administrator — Touchstone already enforces this.

using LibreHardwareMonitor.Hardware;
using System.Text.Json;
using System.Text.Json.Serialization;

var computer = new Computer
{
    IsCpuEnabled        = true,
    IsGpuEnabled        = true,
    IsMemoryEnabled     = true,
    IsMotherboardEnabled = true,
    IsBatteryEnabled    = true,
    IsStorageEnabled    = true,
    IsNetworkEnabled    = false,
};

try
{
    computer.Open();
}
catch (Exception ex)
{
    Console.Error.WriteLine($"SensorDump: failed to open hardware: {ex.Message}");
    return 1;
}

var sensors = new List<SensorEntry>();

foreach (var hardware in computer.Hardware)
    CollectSensors(hardware, null, sensors);

computer.Close();

var options = new JsonSerializerOptions
{
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    WriteIndented          = false,
};

Console.WriteLine(JsonSerializer.Serialize(sensors, options));
return 0;

// ── Helpers ──────────────────────────────────────────────────────────────────

static void CollectSensors(IHardware hardware, string? parentName, List<SensorEntry> list)
{
    hardware.Update();
    foreach (var sensor in hardware.Sensors)
    {
        list.Add(new SensorEntry(
            Hardware : hardware.Name,
            Parent   : parentName,
            Type     : sensor.SensorType.ToString(),
            Name     : sensor.Name,
            Value    : sensor.Value.HasValue ? (double?)Math.Round((double)sensor.Value.Value, 2) : null
        ));
    }
    foreach (var sub in hardware.SubHardware)
        CollectSensors(sub, hardware.Name, list);
}

// ── Data types ───────────────────────────────────────────────────────────────

record SensorEntry(
    [property: JsonPropertyName("hardware")] string  Hardware,
    [property: JsonPropertyName("parent")]   string? Parent,
    [property: JsonPropertyName("type")]     string  Type,
    [property: JsonPropertyName("name")]     string  Name,
    [property: JsonPropertyName("value")]    double? Value
);
