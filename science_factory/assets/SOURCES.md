# Verified celestial imagery

Earth and Moon visuals are derived from the official
[NASA-3D-Resources](https://github.com/nasa/NASA-3D-Resources) repository,
under `Images and Textures/Earth (A)` and `Images and Textures/Moon`.

| Output | Primary source | Original Git blob SHA-1 |
| --- | --- | --- |
| `earth_disc.png` | [Earth (A).jpg](https://github.com/nasa/NASA-3D-Resources/blob/master/Images%20and%20Textures/Earth%20(A)/Earth%20(A).jpg) | `6adcb9237e3240b804bc4b932aadd8a08635054d` |
| `moon_disc.png` | [Moon.jpg](https://github.com/nasa/NASA-3D-Resources/blob/master/Images%20and%20Textures/Moon/Moon.jpg) | `e39f899b3f37e39c75acbe405018157dcfba8b0b` |

`provenance.json` also stores SHA-256 hashes for the original NASA image bytes
and the generated PNGs. The source imagery was verified against its Git blob
hash before processing. The Earth is a fixed, orthographic front hemisphere
projected from NASA's equirectangular global map. The Moon is a face-on NASA
photograph, cropped to the visible lunar disc. These are still 2.5D sprites,
not independently rotating or relit 3D meshes.

The asset-conversion script is `scripts/prepare_celestial_assets.py`.
Normal video rendering reads only these committed PNGs, with no network access.

NASA's [media usage guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)
generally allow re-use of NASA imagery, including commercial use, subject to
third-party copyrights, endorsement and identity restrictions. Check the source
and NASA's current rules before reusing the images in new contexts. Avoid NASA
logos and suggestions of agency endorsement.
