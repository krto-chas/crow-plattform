# Pass 70 – OVK mobile field UI

## Scope

Pass 70 exposes the Pass 69 field domain as a functional mobile-oriented Workbench surface.
It intentionally does not implement final visual design, offline persistence, binary media upload,
or sync conflict resolution.

## Delivered

- `/ovk/falt` touch-oriented field workflow.
- Flow: inspection -> apartment/premises -> room -> defect -> photo metadata.
- Defect taxonomy from `crow_ovk_field` exposed through `/api/ovk/field/defect-types`.
- Browser camera/file capture uses `accept="image/*"` and `capture="environment"`.
- The active apartment/premises number and defect type are inherited automatically by photo evidence.
- Browser Web Crypto calculates SHA-256 before photo metadata is added to the field record.
- `/api/ovk/field/validate` maps the UI payload into the canonical Pass 69 dataclasses and runs `validate_field_data`.
- Existing OVK entitlement remains the access boundary for `/api/ovk/...`.

## Evidence boundary

The browser-selected binary image is not persisted or uploaded in this pass. `local_uri` is a session marker
only and `sync_status=local` describes the metadata record. Pass 70 must therefore not be described as offline
storage or media sync.

## Next pass

Pass 71 should add offline persistence for inspection/field metadata and media blobs, including an installable
app shell/service worker and a local store that survives browser restarts before any server sync is attempted.
