# The prompt

Paste this into a fresh Claude Code session started in the demo directory
(see [SETUP.md](SETUP.md)). Fill in the four `<...>` values first. Don't add
anything else: the prompt is the only input the video shows.

```text
Lifts and escalators on the London Underground break down all the time. A
broken escalator at a busy station means crowding on the stairs; a broken
lift strands anyone who needs step-free access. There are only so many
engineers to send.

Build a web app on Foundry for a station duty manager. It should rank
today's lift and escalator outages at Tube stations by impact (how busy the
station is, and whether step-free access is lost), and let them assign an
engineer to an outage and track its status.

TfL publishes the data:
- current disruptions at Tube stations: https://api.tfl.gov.uk/StopPoint/Mode/tube/Disruption
- lift outages: https://api.tfl.gov.uk/Disruptions/Lifts/v2/
- daily entries and exits per station: https://crowding.data.tfl.gov.uk/Network%20Demand/StationFootfall_2025_2026%20.csv

Use pltr for everything in Foundry. Work in "/pltr demos/station-outages";
the Python transforms repository there is cloned at ./transforms. The app's
Developer Console application is <application-rid>, its OAuth client ID is
<client-id>, and it will be hosted at https://<subdomain>. If something
needs the Foundry UI, stop and tell me exactly what to create. Ask me before
you apply an action or deploy.
```

## Values to fill in

| Placeholder | Where to find it |
|---|---|
| `<application-rid>` | Developer Console: the application's RID. |
| `<client-id>` | Developer Console: the application's OAuth client ID. |
| `<subdomain>` | Developer Console: the approved website subdomain, a full hostname. |
| The folder path | Only if you used a different folder in setup. |

## A harder variant, for a second take

Replace the three data links with:

```text
TfL publishes open data at https://tfl.gov.uk/info-for/open-data-users/.
```

The agent then has to find the endpoints itself. Try it in the rehearsal
only after the main prompt works end to end.
