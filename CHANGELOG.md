# Changelog

## [0.3.0](https://github.com/RJS138/touchstone/compare/v0.2.2...v0.3.0) (2026-03-29)


### Features

* rewrite live ISO for PySide6/Qt — X11 session, Qt system libs, root autologin ([3a8a4eb](https://github.com/RJS138/touchstone/commit/3a8a4eb900da95825609f10530c50e4a060f439f))


### Bug Fixes

* retry smartctl with explicit -d nvme/-d sat on Windows when auto-detect returns no SMART data ([508246d](https://github.com/RJS138/touchstone/commit/508246d3d530507fe335008dec9b8fb03a7c19c3))
* show 'run as Administrator' when smartctl is present but SMART data missing ([9d1fc1c](https://github.com/RJS138/touchstone/commit/9d1fc1c4c11a205cc5aea5959a1650426224f228))

## [0.2.2](https://github.com/RJS138/touchstone/compare/v0.2.1...v0.2.2) (2026-03-29)


### Bug Fixes

* retry hdiutil DMG creation up to 5 times to handle CI resource busy ([45219c1](https://github.com/RJS138/touchstone/commit/45219c1cdeffdb80097afc78081a04b2e8d78d8e))

## [0.2.1](https://github.com/RJS138/touchstone/compare/v0.2.0...v0.2.1) (2026-03-29)


### Bug Fixes

* hotfix workflow create-release gated on version input, not tag ref ([863ed4e](https://github.com/RJS138/touchstone/commit/863ed4e2952ef44752b16e5b9f49ede3e8f38055))
* wire build pipeline into release-please workflow ([0191881](https://github.com/RJS138/touchstone/commit/019188137e2e7d1bbe7a1fd615b9bafbdf447e3c))

## [0.2.0](https://github.com/RJS138/touchstone/compare/v0.1.9...v0.2.0) (2026-03-29)


### Features

* -&gt; minor bump | fix: -&gt; patch bump | feat!: -&gt; major bump ([fdce051](https://github.com/RJS138/touchstone/commit/fdce051bf4da04867a2a43d659ca99ca11956d70))
* derive app version from git tag — no more manual version bumps ([6fdd1ed](https://github.com/RJS138/touchstone/commit/6fdd1edfb13ebf814e344ddf44732826b71443ab))
* download touchstone-live.iso onto Ventoy USB so live Linux boot works ([527266c](https://github.com/RJS138/touchstone/commit/527266c6ae0d669879f895afb6d46e116c2b4a85))


### Bug Fixes

* harden release CI — safe version stamping, PR title enforcement, release body ([c3a0960](https://github.com/RJS138/touchstone/commit/c3a096056b13ed1887ef7de329b0d0c463137e0c))
* rename PC Tester to Touchstone in live ISO build config comment ([1021a07](https://github.com/RJS138/touchstone/commit/1021a07dcb9759b1baaa1ff26803d10be9c414fe))
* restore packages block in release-please config and set bootstrap-sha ([f278eea](https://github.com/RJS138/touchstone/commit/f278eead57decf8b330f83c3714051a7ea019c72))

## Changelog

All notable changes to Touchstone are documented here.
release-please maintains this file automatically — do not edit by hand.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- release-please inserts new entries above this line -->
