# Trickster — verified maintenance data source notes

Generated 2026-08-29 for Boat Maintenance Data schema 1.1.0.

## Verification rule
Only equipment identities already confirmed for Trickster and maintenance facts supported by manufacturer manuals/manufacturer documentation were loaded. No current hour readings, previous service dates, inventory quantities, exact installation dates, or unknown component models were guessed. All recurring-task baselines are therefore blank. The app should show **Needs info** until you enter current meter hours and either backfill a verified prior service or log the next service.

## Included equipment
- Lugger LP668D main engine — Trickster configuration is keel-cooled, dry-stack, naturally aspirated.
- Northern Lights M753K.3 8 kW generator — M753K OEM operator manual used for verified family maintenance items.
- Yanmar 3YM30AE wing/get-home engine.
- Side-Power/Sleipner SP155 TC bow thruster.
- Side-Power/Sleipner SP155 TC stern thruster.
- Naiad 174-1 stabilizers, assembly 0136, serial 04074888.
- Maxwell VWC2200 windlass.
- Four-battery Lifeline 8D AGM house bank.

## Sources
1. Lugger LP445/LP668D/T Operator's Manual OLP 05/00 (manual mirror): https://manualzz.com/doc/68520442/lugger-lp668t-marine-engine-operator-s-manual
2. Northern Lights M753K Operator's Manual O753K 10/09 (official PDF): https://www.northern-lights.com/media/PDFs/manual_pdfs/O753K.pdf
3. Yanmar YM Series Operation Manual covering 3YM30AE (official PDF): https://www.yanmar.com/marine/wp-content/uploads/2020/03/0AYMM-M0002E_2025.02.pdf
4. Side-Power SP155 TC/SP200 TC/SP220 TC/SP285 TC user manual (manual mirror): https://manualzilla.com/doc/7374231/side-power-sp-155-tc-i-user-s-manual
5. Sleipner current SP155 anode compatibility: https://www.sleipnergroup.com/thruster-systems/spare-parts/anodes/anode-zinc-se170-sp155-220-285
6. Naiad Stabilizer Models 162-254 owner handbook (manual mirror): https://www.scribd.com/document/902360170/Naiad-Stabiliser-Models-162-254-Datum-Owners-Handbook
7. Maxwell 2200 VW/VWC/VWCLP manual (manual mirror): https://manualzz.com/doc/6639860/2200-vw-vwc-vwclp-manual
8. Lifeline AGM Technical Manual Rev. G (official PDF): https://lifelinebatteries.com/wp-content/uploads/2015/12/6-0101G_Lifeline_Technical_Manual.pdf

## Deliberate exclusions
The following are not preloaded because the exact installed model/configuration or a model-specific maintenance recommendation has not been verified for this dataset: main transmission/reduction gear; watermaker; reverse-cycle HVAC units; toilets; current inverter/charger maintenance; specific bilge pumps; davit/hoist service; steering hydraulics; fire-suppression model; tender outboard; and most navigation/electronics.

For the LP668D main engine, raw-water impeller and heat-exchanger cleaning tasks were deliberately excluded because Trickster's main is keel-cooled and the LP668 manual identifies the raw-water pump service as heat-exchanger-cooled-engine-only.

For the Naiad 3-year oil/seal intervals, the handbook also says 4000 operating hours, whichever comes first. A 4000-hour trigger is not fabricated because no reliable stabilizer operating-hours meter has been confirmed on Trickster.

For the Yanmar coolant and marine-gear oil, the exact installed coolant formulation and gear model/configuration are not verified here, so those fluid-change entries were not preloaded even though the YM manual discusses them.


## Yanmar 3YM30AE — initial 50-hour service and break-in

Source: Yanmar Marine International, **YM Series Operation Manual**, revision 2025.02
(official Yanmar download for the 2YM15 / 3YM20 / 3YM30AE series).

Verified initial 50-hour maintenance imported:
- Drain fuel tank.
- Change engine oil and replace engine-oil filter element.
- Change marine-gear oil and replace marine-gear oil filter, if equipped.
- Check/adjust alternator V-ribbed belt tension.
- Inspect/adjust intake and exhaust valve clearance.
- Check/adjust remote-control cables.
- Check/adjust propeller-shaft alignment.

Verified break-in guidance was also added to the Wing Engine notes. No marine-gear oil type,
capacity, filter part, or valve-clearance specification was added because the installed gear/model
details and exact service data were not independently verified for Trickster in this update.
