# Programming a show with cross-vehicle animations
With the tesla_xlights_cross_vehicle_folder, you can program synchronized light shows with cross-vehicle animations for up to 5 vehicles at once.

## Setup xLights
This guide assumes that you have already setup the global xLights settings and read the instructions for creating normal light shows.

1. Download and unzip [tesla_xlights_cross_vehicle_folder.zip](/xlights/tesla_xlights_cross_vehicle_folder.zip?raw=true), which is the Tesla xLights bare project directory.
2. Change your xLights show directory to tesla_xlights_cross_vehicle_folder
    - You can select 'Change Temporarily' if you want xLights to continue opening the normal show directory when starting the program.

    <img src="/images/change_directory.png?raw=true" width="450" />

3. Create a new sequence with the usual settings. Select the 'All Cars' view.

    <img src="/images/view_all_cars.png?raw=true" width="600" />

## Layout
- In the preview, you will find five Cybertruck's in a row with five Model S' stacked above them. This accomodates all lights and closures for all 
vehicle types. It's recommended to resize or move the preview to fit all cars.

    <img src="/images/preview_moved.png?raw=true" width="1000" />

- Each Cybertruck / Model S combination has it's own number. When viewed from the front, the cars are numbered 1 to 5 from Left to Right.

    <img src="/images/car_setup.jpg?raw=true" width="800" />


- This show folder heavily relies on Groups to organize the almost 1000 light channels.
    - Make yourself familiar with the Groups before you start programming effects.
    - All Groups can be expanded by double clicking them in the timeline. Most can be expanded multiple times.
    - You can place the 'On' Effects directly on the groups to turn on all lights in the group.

## Programming tips
- Get started by only using a small set of groups and don't program the individual lights. Group recommendations for getting started:
    - _Front 1_ to _Front 5_, and _Rear 1_ to _Rear 5_ (located in _All Front Lights_ and _All Rear Lights_)
    - Groups _All Channel 4-6, All Signatures, All Inner Main Beam, All Outer Main Beam, All Front Turns_.
    - For Cybertruck: _Front Light Bar 1-5_, and _Rear Light Bar 1-5_, located in _All Front Lightbars_ and _All Rear Lightbars_
- You can use xLights' integrated effects, e.g. the Curtain effect, on the following channels:
    - Front Light Bar 1-5
    - Rear Light Bar 1-5
    - Front 1-5
    - Rear 1-5
    - Do not use integrated effects on any other channel, including _All Front Lightbars_, _All Front Lights_, etc. They will not play as previewed in xLights.
- To create cross-vehicle 'sweeping' effects on the Cybertruck light bar, or the normal lights, align the 'Curtain' effect to play successively on each car. Place 'On' effects as necessary.
    - Tip: Right click on the timing track and use 'Divide Timings' to split a time segment into 5 equal segments.

    <img src="/images/sweep_example.gif?raw=true" width="1000" />

## Exporting the show
Before you can enjoy the show on up to five vehicles, you need to export the effects to one xLights sequence for each car.

1. Save your cross-vehicle project and close xLights.
2. Reopen xLights with the default show directory for only one car loaded.
3. Create a New Sequence with the same settings and audio file used in the cross-vehicle sequence. Select the 'Multishow Import View'
4. Select Import -> Import Effects and select your cross-vehicle sequence (.xsq file)

    <img src="/images/convert_import.png?raw=true" width="500" />

5. Select 'Load Mapping' and choose cross_vehicle_mapping_1.xmap (located in tesla_xlights_cross_vehicle_folder).

    <img src="/images/convert_load_mapping.png?raw=true" width="800" />

6. Uncheck 'Lock effects on import' and select 'Ok'
7. IMPORTANT: Press "Render All" and save the sequence.

    <img src="/images/convert_render_all.png?raw=true" width="300" />
8. Repeat steps 3-7 for each car.