# **Tesla Light Show xLights Guide**

Welcome to the Tesla Light Show xLights guide! You can create and run your own light shows on Tesla vehicles.

<img src="/images/xlights_overview.png?raw=true" width="1000" />

## Running a custom show on a vehicle
A custom show can be run on a supported vehicle by loading it via a USB flash drive. Create and share your shows with others! A single show can be shared and run on any supported vehicle; they are not model-specific. The sequence data is stored in a .fseq file and the music comes from your choice of .mp3 or .wav.
### Download a Show
Multiple light show repositories can be found online. A screenshot from [XLightShows](https://xlightshows.io/) and [TeslaLightShare.io](https://teslalightshare.io/) is below.

<a href="https://xlightshows.io/"><img src="/images/xlightshows_screenshot.png?raw=true" width="1000"/></a>

<a href="https://teslalightshare.io/"><img src="/images/tesla_light_share_screenshot.png?raw=true" width="1000"/></a>

### Supported Vehicles
- Model S (2021+)
- Model 3
- Model X (2021+)
- Model Y
- Cybertruck
- Running Software v11.0 (2021.44.25) or newer
### USB flash drive requirements
- Must contain a base-level folder called "LightShow" (without quotation marks and case sensitive).
- The LightShow folder must contain at least 2 files:
  - a show .fseq file
  - a show .mp3 or .wav file (wav is recommended)
- The fseq filename must match the mp3/wav filenames
    - E.g., show1.fseq/show1.wav can exist with show2.fseq/show2.mp3
- Multiple shows can be stored on 1 USB drive (2023.44.25+ Vehicle Software).
- Must be formatted as exFAT, FAT 32 (for Windows), MS-DOS FAT (for Mac), ext3, or ext4. NTFS is currently not supported.
- Must **not** contain a base-level TeslaCam folder.
- Must **not** contain any map update or firmware update files.
### Running the custom light show on a vehicle
- Insert the flash drive into one of the front USB, USB-C ports, or glovebox USB port, then wait a few seconds.
- In Toybox, select Light Show and tap Schedule Show.

    <img src="/images/start_show_button.png?raw=true" width="315" />

- If the files on the USB flash drive meet the requirements, then the custom shows will be available to select from the drop-down menu.

    <img src="/images/multi_select_usb.png?raw=true" widtht="442" />

### Light Show Community
[reddit.com/r/TeslaLightShow/](https://www.reddit.com/r/TeslaLightShow/)

### Debug
- If the popup title is "Light Show" instead of "Custom Light Show", then the requirements are not being met for the USB flash drive formatting and/or required folder and files.
- Error messages will be provided if the required files exist but there is a problem with the light show sequence file.

## <a name="show_limits"></a>General Limitations of Custom Shows
- The maximum duration for a custom Tesla xLights show is 4 hours.
- The limit on number of commands during a custom show has been removed.
## Audio file requirements
You can use both the mp3 and wav format (.wav is recommended).
Make sure the file is encoded with a sample rate of 44.1 kHz; less common 48 kHz files won't properly sync to the light show.

## <a name="getting_started"></a>Getting started with the Tesla xLights project directory
1. Visit [xLights Downloads](https://xlights.org/releases/) to download and install the xLights application.
2. Download and unzip [tesla_xlights_show_folder.zip](xlights/tesla_xlights_show_folder.zip?raw=true), which is the Tesla xLights bare project directory.
   - It is recommended to keep the project directory structure as-is and leave all files in their default locations.
3. Open the xLights application.
4. **IMPORTANT:** In File > Preferences > Sequences > FSEQ Version, select "V2 Uncompressed".

    <img src="/images/v2_uncompressed.png?raw=true" width="500" />

5. In File > Select Show Folder, navigate to and select the unzipped project directory, then select Open.
6. Select the Layout tab to view the Tesla 3D vehicle model.
7. Make sure that the 3D preview checkbox is selected.

    <img src="/images/3d_preview.png?raw=true" width="750" />

8. Select the Sequencer tab.

    <img src="/images/xlights_layout.png?raw=true" width="950" />

9. Note that the previewed Tesla Model S combined with the Cybertruck include the superset of lights and closures that are needed for all supported vehicles, and should be used to generate shows for all vehicle types. See [light channel locations](#light-channel-locations) for information about where the lights are on each vehicle.

## Opening the example sequence
An example sequence is provided that can be run on the vehicle and/or opened in xLights. These instructions cover how to open it in xLights.
1. Follow the [getting started](#getting_started) instructions to set up the xLights project.
2. Download and unzip the example light show:
[lightshow_example_1_elevator_music.zip](examples/lightshow_example_1_elevator_music.zip?raw=true)
or
[lightshow_example_2_Max_Carlisle_Auld_Lang_Syne_In_the_City.zip](examples/lightshow_example_2_Max_Carlisle_Auld_Lang_Syne_In_the_City.zip?raw=true).
3. In File > Open Sequence, navigate to the unzipped folder and select the ```lightshow.xsq``` example file, then select Open.
4. In the Sequencer tab, double click groups in the timeline to reveal individual left / right control.

     <img src="/images/xlights_demo_track.png?raw=true" width="900" />

## Creating a new sequence
1. Follow the [getting started](#getting_started) instructions to set up the xLights project.
2. Select File > New Sequence.
3. Select Musical Sequence.
4. Navigate to your chosen .wav or mp3 file, select it, then select Open. Note that .wav files may be hidden unless file type is set to xLights Audio Files.

    <img src="/images/wav_hidden.png?raw=true" width="450" />

5. In the Wizard tab select Custom.
6. Change the Frame interval to 20ms then select OK.

     <img src="/images/sequence_setting_20ms.png?raw=true" width="500" />

    Note: any value between 15ms and 100ms is supported by the vehicle, but 20ms is recommended for nearly all use cases. The [maximum show size limits](#show_limits) do not depend on the frame interval.

7. Select Quick Start and wait for the sequencer to load.
8. In the top left of the timeline, select "Group View" in the view selector. You can also choose "Old View" for the pre-update layout.

    <img src="/images/groups_select_view.png?raw=true" width="450" />

9. If using the recommended "Group View", you can double click the light groups to reveal and hide individual left/right control. Placing light effects in the group object will activate both the left and right light.

    <img src="/images/groups_left_right.png?raw=true" width="450" />

10. If using the old view, double click on "GRP Tesla Model S" to view all channels.

    <img src="/images/all_lights_closures_old.png?raw=true" width="450" />

11. For more information on the workflow of creating xLights sequences, please use existing online resources. The rest of these instructions contain Tesla-specific information for show creators.

## Light Show Sequence Validator Script
A Python [validator.py](validator.py) script is provided to help check if your custom light show sequence meets these limitations, without needing a Tesla vehicle.

Windows user can run validator.py by double clicking the file. Drag and drop the .fseq file into the new window.

Users who do not have Python installed can instead use [validator-windows.exe](validator-windows.exe?raw=true) or [validator-macos](validator-macos.zip?raw=true) (on macOS, run with Ctrl + Left Click -> Open).

Alternatively, run:
```
python validator.py lightshow.fseq
```
macOS users should use this command instead:
```
python3 validator.py lightshow.fseq
```

Expected output looks like:
```
> python validator.py lightshow.fseq
Found 2247 frames, step time of 20 ms for a total duration of 0:00:44.940000.
```

## Boolean Light Channels
Most lights available on the vehicle can only turn on or off instantly, which corresponds to 0% or 100% brightness of an 'Effect' in xLights.
- For off, use blank space in the xLights timeline
- For on, place *Turn On; Instant* (hotkey: 'F' on your keyboard)

The minimum on-time for boolean light channels to produce light is 15ms, although human eyes will have a hard time seeing anything this short! Minimum on-time or off-time of 100ms generally makes the show more pleasing to look at.

In this example, the Left Front Fog turns on and off 3x:

<img src="/images/on_effect_example.png?raw=true" width="550" />

## <a name="ramping_lights"></a>Light Channels with Brightness Control
Some channels can have a slow ramp in the intensity during turn-on or turn-off, to create graceful visual effects. Some even allow for full brightness control:
| Channel | Model S | Model X | Model 3/Y | Cybertruck |
| --- | --- | --- | --- | --- |
| Outer Main Beam  | Ramping on LED reflector headlights; <br> Boolean on LED projector headlights | Ramping on LED reflector headlights; <br> Boolean on LED projector headlights | Ramping on LED reflector headlights; <br> Boolean on LED projector headlights | Ramping |
| Inner Main Beam | Ramping | Ramping | Ramping | Ramping |
| Signature | Boolean | Boolean | Ramping | - |
| Channels 4-6 | Ramping | Ramping | Ramping | - |
| Front Turn | Boolean | Boolean | Ramping | Ramping |
| Front Side Markers | Boolean | Boolean | Boolean | Ramping |
| Front Light Bar | - | - | - | Full Brightness Control |
| Offroad Light Bar | - | - | - | Full Brightness Control |
| Rear Light Bar | - | - | - | Full Brightness Control |
| Brake Light | Boolean | Boolean | Boolean | Full Brightness Control |
| Rear Turn | Boolean | Boolean | Boolean | Full Brightness Control |
| Bed Lights | - | - | - | Boolean |

Cybertruck Bed Lights always ramp on and off with a 500 ms duration, even with 'Turn on/off; Instant' effects.

### Ramping light channels
To command a light to turn on or off and follow a ramp profile, place the effect with the corresponding keyboard shortcut:

| Ramping Function | xLights Effect Brightness | Hotkey
| ------ | ----------- | ----------- |
| Turn off; Instant | 0% | *empty timeline* |
| Turn off; 500 ms | 10% | W |
| Turn off; 1000 ms | 20% | S |
| Turn off; 2000 ms | 30% | X |
| Turn on; 500 ms | 70% | E |
| Turn on; 1000 ms | 80% | D |
| Turn on; 2000 ms | 90% | C |
| Turn on; Instant | 100% | F |

The keyboard layout is designed to be easy to use. Note that the effect types are grouped into vertical keyboard rows and sorted by duration.

<img src="/images/keyboard_shortcuts.png?raw=true" width="800" />

#### Other notes
- Ramping can only prolong the time it takes to fully turn a light on or turn off. It is not possible to command a steady-state brightness setpoint between 0% and 100% intensity.
- If an xLights effect is longer than the ramping duration, then the light will stay at 0% or 100% intensity after it finishes ramping.
- Ramping effects can end early or be reversed before completion, and the light will immediately start following the new profile that is commanded.
- To guarantee that a light reaches the 0% or 100% setpoint, the xLights effect must have a duration at least 50ms greater than the ramp duration. Conversely, to guarantee that a light does not fully reach the 0% or 100% setpoint, the xLights effect must have a duration at least 100ms less than the ramp duration.
- Ramping Channels 4-6 have some unique aspects compared to other lights in order to use them effectively - see notes in [Ramping Channels 4-6](#ramping_channels_4_6).

#### Ramping light examples
- Left inner main beam, *Turn on; 2000 ms*, effect duration 1s: causes the light to ramp from 0% to 50% intensity over 1s, then instantly turn off (because of the empty timeline).

    <img src="/images/ramp_example_1.png?raw=true" height="180" />

- Left inner main beam, *Turn on; 2000 ms*, effect duration 4s: causes the light to ramp from 0% to 100% intensity over 2s, then stay at 100% intensity for 2s, then instantly turn off after 4s.

    <img src="/images/ramp_example_2.png?raw=true" height="180" />

- Left inner main beam, *Turn on; 2000 ms* for 2.06s, *Turn off; 2000 ms* for 1.9s, *Turn on; 2000 ms* for 2.06s: causes light to ramp to 100% intensity, then down close to, but not reaching, 0% intensity, then back up to 100% intensity, then instantly turn off.

    <img src="/images/ramp_example_3.png?raw=true" height="180" />

### Full Brightness Control Channels
Some lights on Cybertruck have full brightness control. Their brightness always corresponds to the value set in xLights.
- Place an 'On' Effect using the shortcut _F_. Lights can be set to a steady-state brightness setpoint between 0% and 100% intensity using the 'Brightness' slider in the 'Colors' window.

    <img src="/images/brightness_slider.png?raw=true" width="500" />
    
- Custom ramp durations can be achieved using 'Value Curves'. The menu is opened when clicking the green arrow next to the brightness slider. To create a basic ramp, select 'Ramp' from the drop-down list and set the start/end duration to 0%/100%. The light will reach 0%/100% brightness at the end of the 'On' effect.

  <img src="/images/value_curve.png?raw=true" width="900" />
  
- Value Curves can also be used to create more advanced custom brightness effects. Keep in mind that the maximum brightness is 100.
- On cars without full brightness control, any brightness setting above 50% will set the light to ON and otherwise it will be OFF.

## <a name="light_locations"></a>Light Channel Locations
The following tables and images help show which channels are controlled on each car. Some vehicles have lights that do not exist, or have multiple lights driven by the same control output - see notes in [Light channel mapping details](#light_channel_mapping_details) for this information.
| Light Channel Name | Identifier in image - Model S/X | Identifier in image - Model 3/Y |
| --- | --- | --- |
| Outer Main Beam | 1 | 1 |
| Inner Main Beam | 2 | 2 |
| Signature | 3 | 3 |
| Channel 4 | 4 | 4-6 |
| Channel 5 | 5 | 4-6 |
| Channel 6 | 6 | 4-6 |
| Front Turn | 7 | 7 |
| Front Fog | 8 | 8 |
| Aux Park | 9 | 9 |
| Side Marker | 10 | 10 |

### Model 3/Y with LED reflector lamps
<img src="/images/3_headlights_reflector.png?raw=true" width="900"/><br>

### Model 3/Y with LED projector lamps
<img src="/images/3_headlights_projector.png?raw=true" width="900"/><br>

### Model S with LED reflector lamps
<img src="/images/s_headlights_reflector.png?raw=true" width="900"/><br>

### Model S with LED projector lamps
<img src="/images/s_headlights_projector.png?raw=true" width="900"/><br>

### Model X
<img src="/images/x_headlights.png?raw=true" width="900"/><br>

### Cybertruck

<img src="/images/cybertruck_front.png?raw=true" width="900"/><br>
<img src="/images/cybertruck_rear.png?raw=true" width="900"/><br>
<img src="/images/lightbar_rear.png?raw=true" width="900"/><br>

## <a name="closures"></a>Closures channels
In custom xLights shows, the following closures can be commanded:
| Channel | Model S | Model X | Model 3/Y | Cybertruck | Supports Dance? | Command Limit Per Show |
| --- | --- | --- | --- | --- | --- | --- |
| Liftgate | Yes | Yes | Only vehicles with power liftgate | Yes (Frunk) | Yes | 6 |
| Mirrors | Yes | Yes | Yes | Yes | - | 20 |
| Charge Port | Yes | Yes | Yes | Yes | Yes | 3 |
| Windows | Yes | Yes | Yes | Yes | Yes | 6 |
| Door Handles | Yes | - | - | - | - | 20 |
| Front Doors | - | Yes | - | - | - | 6 |
| Falcon Doors | - | Yes | - | - | Yes | 6 |

To command a closure to move in a particular manner, place an effect with the following keyboard shortcuts:

| Closure Movement | xLights Effect Brightness |
| --- | --- |
| Idle | *empty timeline* |
| Open | Q |
| Dance | A |
| Close | Z |
| Stop | F |

### Definitions for closure movements:
- **Idle:** The closure will stop, unless the closure is in the middle of an Open or Close in which case that movement will finish first.
- **Open:** The closure will open and then stop once fully opened.
- **Dance:** Get your party on! The closure will oscillate between 2 predefined positions. For the charge port, Dance causes the charge port LED to flash in rainbow colors.
- **Close:** The closure will close and then stop once fully closed.
- **Stop:** The closure will immediately stop.

### Other notes
- For closures that do not support Dance, it's recommended to use Open and Close requests to cause movement during the show.
- It's recommended to avoid closing windows during the show so that music stays more audible. Music only plays from the cabin speakers during the show.
- Closures can only dance for a limited time before encountering thermal limits. This depends on multiple factors including ambient temperature, etc. If thermal limits are encountered, the given closure will stop moving until it cools down. Dancing for ~30s or less per show is recommended.
- Moving Windows during Model X door movement can cause false pinch detections, stopping the light show.

### Closures Command Limitations
- All closures have actuation limits listed in the table above. Only Open, Close, and Dance count towards the actuation limits. The limits are counted separately for each individual closure.
- With the exception of windows, closures will not honor Dance requests unless the respective closure is already in the open position. The show creator must account for this by adding a delay between Open and Dance requests. Refer to [Closure Movement Durations](#closure_movement_durations) for more information.
- The charge port door will automatically close if 2 minutes have elapsed since opening.
- Closure commands spaced very close together (eg, 20ms) will not cause much visible movement, and will use up the command limits quickly. Leave reasonable time between commands to see the best effects.

### Closures Command xLights Notes
- For Idle, Open, Close, and Stop, there is no minimum xLights effect duration in order for the command to take effect. For example, the following sequence has a liftgate open command with duration of only 1s ahead of the dance that comes later, and this is sufficient to open the liftgate all the way:

    <img src="/images/open_and_dance.png?raw=true" width="850" />

- For Dance, the xLights effect must persist until the dancing is desired to stop.

### <a name="closure_movement_durations"></a>Closure Movement Durations
| Closure Movement | Approximate Duration (s) |
| --- | --- |
| Open Liftgate | 14 |
| Close Liftgate | 4 |
| Open Front Doors | 22 |
| Close Front Doors | 3 |
| Open Falcon Doors | 20 |
| Close Falcon Doors | 8 |
| Windows | 4 |
| Mirrors, Door Handles, Charge Port | 2 |

## Tips for platform-agnostic light shows
### Light channel mapping recommendations
- Not all vehicles have all types of lights installed. When turning on/off lights in sync with key parts of the music's beat, try to use lights that are installed on all vehicle variants.
- Not all vehicles have individual control over every light. In these cases, multiple xLights channels are OR'd together to decide whether to turn on a given group of lights. These are outlined in the section below.
- For lights that are controlled by multiple OR'd channels, keep in mind that some shared off-time on **all** of the OR'd channels is required to cause an apparent flash of the light.
    - This example will cause Aux Park lights to turn on constantly on Model 3/Y:

        <img src="/images/ord_channel_not_ok.png?raw=true" width="900" />

    - This example will cause the Aux Park lights to flash on Model 3/Y (note the blank time between each box compared to the other example):

        <img src="/images/ord_channel_ok.png?raw=true" width="900" />

### <a name="light_channel_mapping_details"></a>Light channel mapping details
#### Side Markers and Aux Park
- Side markers are only installed in North America vehicles
- Aux park are not installed in Model 3 Standard Range +
- On Model 3/Y, all aux park and side markers operate together. They will activate during ```(Left side marker || Left aux park || Right side marker || Right aux park)``` requests from xLights.
- On Model S, aux park and side markers operate together, but they have independent left/right control. They will activate during the following requests from xLights:
   - Left side: ```(Left side marker || Left aux park)```
   - Right side: ```(Right side marker || Right aux park)```

#### <a name="ramping_channels_4_6"></a>Ramping Channels 4-6
- For Model S/X:
    - Individual on/off control is supported for each channel.
    - Only a single ramping duration is allowed between all 3 channels.
    - The ramping duration for all 3 is defined only by the effect placed in xLights for Channel 4.
- For Model 3/Y:
    - All 3 of these channels are combined into a single output on the vehicle, see [light channel locations](#light_locations).
    - The on/off state is OR'd together between all 3 channels: ```(Channel 4 || Channel 5 || Channel 6)```.
    - The ramping duration is defined by the effect placed in xLights for Channel 4.
- Because channel 4 acts as the leader for setting ramping duration on all platforms, a ramping effect must sometimes be included on Channel 4 even when Channel 4 is not turned on.
    - In this example, each channel blinks 3x and ramps down after its last blink. Notice how an *Turn Off, 500ms* effect is added always on Channel 4, even when it's Channel 5 or Channel 6 that were turned on.

        <img src="/images/channel_4_6_example.png?raw=true" width="850"/>

    - In this example, Channel 4 & 6 ramp up and ramp down again. Notice how Channel 6 has the *Turn On; Instantly* effect while Channel 4 defines the effect to be *Turn On; 1000ms* for both channels.

        <img src="/images/channel_4_6_example_2.png?raw=true" width="850"/>


#### Front Fog
- Front fog lights are installed in all vehicles except Model 3 Standard Range +.
- Vehicles without front fog lights will not use any other light in place of front fog lights.

#### Rear Fog
- Rear fog lights are installed in non-North America vehicles, and North America Model X.
- Vehicles without rear fog lights will not use any other light in place of rear fog lights.

#### Tail lights and License Plate Lights
- On Model 3 built before October 2020: left tail, right tail, and license plate lights operate together. They will activate during ```(Left tail || Right tail)``` requests from xLights - note that the license plate lights xLights channel will have no effect on these vehicles.

#### Cybertruck Light Bar
- The front light bar has 60 individually controllable LEDs each.
- The rear light bar has 52 individually controllable LEDs each. 
- It's recommended to use xLights' integreated effects to program the light bar. Good ones for getting started are: Curtain, Bars, Marble, Morph and On. Most effects can be customized using the 'Effect Settings' Window. The visualization will display all effects accurately, but keep in mind that the lights are very diffused.

    <img src="/images/xlights_integrated_effects.png?raw=true" width="1000" />

    <img src="/images/effect_settings.png?raw=true" width="500" />
    
- The front light bar is grouped intro three segments: Left, Center, Right. Left/Right are the outer angled portions of the front light bar. The segments can be accessed by double clicking on the light bar in the timeline.

    <img src="/images/lightbar_timeline.png?raw=true" width="900" />
    
- The rear light bar is grouped into the same three segments: Left, Center, Right:
    - The center segment includes all 52 LEDs located on the bed door.
    - In last year's release, 4 LEDs were mistakenly assigned to the left and right segments. These segments are now empty but have been retained for backward compatibility.
        - On a very small amount of exisiting shows, this might generate a "Sequence Element Mismatch" warning when opening them with the updated xLights configuration.
        - You can proceed to open the show by selecting "Delete this element from the sequence".
- Even the individual LEDs can be programmed by double clicking on the segments (Left, Center, Right) in the timeline.

#### Cybertruck Offroad Light Bar
- The offroad light bar is an optional upgrade. Most Cybertrucks won't have them installed.
- The offroad light bar consists of six segments. Two side-facing ditch lights, four forward-facing lights.
- The LEDs can be controlled individually by double clicking the Offroad Light Bar in the timeline, then double clicking 'Strand 1'.

#### Cybertruck Light Remapping
To make old light shows look as good as possible on the new Cybertruck's lights, the following channels are remapped:
- Reverse Lights are activated with L/R Tail in xLights for individual L/R control.
- L/R Rear Side Markers are activated with L/R Side Repeaters in xLights.
- Powered Frunk is activated by Liftgate in xLights.
- Frunk Light is activated by Aux Park in xLights.
- Bed Lights are activated with Reverse Light in xLights.
- L/R Rear Turn Signals have been disabled.

#### Interior RGB Lights
- There is full RGB control over the color of the Center Front Display.
    - This visibly lights up the entire interior, even when the show is viewed from outside.
- On cars with Interior Accent Lights, there is full RGB control over each of the five segments:
  - Center Front RGB, L/R Front/Rear RGB.
- All Interior RGB Lights, including the screen are grouped into "All Interior RGB".
    - The groups can be expanded by double clicking for individual control over the segments.
    - The Front Display is brighter than the Accent lights. For most effects, it is recommended to operate them together.
- In xLights, recommended effects for RGB effects are: Color Wash, On.
    - Note: By right-clicking on colors in the Color window, custom color curves can be created with the "On"" effect.

<img src="/images/rgb_interior.png?raw=true" width="800" />

## Converting old show files
Old show files only need to be converted to edit them with the updated xLights configuration. Old light shows can be played without issues on updated Teslas.
All old .xsq and .fseq files are compatible with this light show update.
- On a very small amount of exisiting shows, there might appear a "Sequence Element Mismatch" warning when opening them with the updated xLights configuration.
- You can proceed to open the show by selecting "Delete this element from the sequence".
- This only affects shows which programmed the rear light bar LEDs pixel by pixel.
### Pre-2023 update
All old .xsq and .fseq files are fully compatible with this light show update. You can edit older .xsq files instantly without converting them. Keep in mind that there is no backwards compatibility, once you save them, you won't be able to open them with the old project folder anymore.
### Pre-2022 update
- Create a new folder for the converted project and copy the old audio file over.
- Create a new sequence with the audio file from the new folder.
- Select Import -> Import Effects and choose your old .xsq file.

    <img src="/images/convert_import.png?raw=true" width="500" />

- In "Map Channels" Window, select "Load Mapping" and choose "2022_mapping.xmap" located in the tesla_xlights_show_folder.

    <img src="/images/convert_load_mapping.png?raw=true" width="800" />

- Press "Ok", the old sequence will import. It's recommended to use the "Old View" for working with converted files.

    <img src="/images/convert_old_view.png?raw=true" width="1000" />

- Press "Render All" to see the imported effects in the preview.

    <img src="/images/convert_render_all.png?raw=true" width="300" />

