# Kubernetes manifests

`deployment.yaml` / `service.yaml` / `hpa.yaml` / `secret.example.yaml` are
the real manifests -- written for an actual EKS cluster with an
externally-managed Mongo (Atlas or similar) behind `MONGO_URI`, an image
pulled from ECR, and a real Secret populated out of band (ideally via the
External Secrets Operator, see `docs/ARCHITECTURE.md`). Applying them for
real costs money (see `../terraform/README.md`) and is a separate,
deliberate decision -- not needed to verify the manifests themselves are
correct.

## Testing these manifests for free, locally, on Docker Desktop

Docker Desktop ships its own single-node Kubernetes cluster. Enabling it
costs nothing and needs no AWS account -- it's the fastest way to prove
`deployment.yaml`/`service.yaml`/`hpa.yaml` actually work (probes pass,
the Service routes traffic, the HPA registers) before ever touching real
infra.

**One-time setup:**
1. Docker Desktop -> Settings -> Kubernetes -> check "Enable Kubernetes" ->
   Apply & Restart (~1-2 minutes; restarts Docker Desktop).
2. Confirm: `kubectl config get-contexts` should now list
   `docker-desktop`. Switch to it: `kubectl config use-context docker-desktop`.

**This machine specifically** also has an unrelated real AWS EKS context
configured (`sonicloud-eks`, a different project). Every `make k8s-local-*`
target below refuses to run unless the current `kubectl` context is
exactly `docker-desktop`, on purpose -- there is no scenario where these
targets should ever touch a real cluster.

**Then:**
```bash
make k8s-local-up      # trains the model, builds :local, applies the local/ overlay, waits for rollout
make k8s-local-status  # pods/service/HPA status
kubectl port-forward svc/transit-satisfaction-api 8000:80
curl localhost:8000/health
curl -X POST localhost:8000/predict -H "Content-Type: application/json" \
  -d '{"text": "Bus delayed again near Embarcadero station"}'
make k8s-local-down    # tear down when finished
```

`infra/k8s/local/` is a [Kustomize](https://kustomize.io/) overlay, not a
copy of the real manifests: `kustomization.yaml` references
`../deployment.yaml`/`../service.yaml`/`../hpa.yaml` directly (so the real
manifests are exactly what gets tested, never a drifted duplicate),
retargets the image to a locally-built tag instead of ECR, drops the
replica count to 1 (a single-node local cluster doesn't need 2), and adds
two things that only exist for local testing: an in-cluster MongoDB
(`local/mongo.yaml` -- the real setup deliberately has no in-cluster
database) and a `secretGenerator`-produced Secret containing a plain local
connection string, not a real credential.

### Known limitation: the HPA won't actually scale locally

`hpa.yaml` applies cleanly, but Docker Desktop's local cluster has no
`metrics-server` installed by default, so `kubectl get hpa` will show the
CPU target as `<unknown>` and it won't actually scale pods up/down. That's
expected -- this local setup proves the manifest itself is valid and
accepted by the API server, not that autoscaling behavior works
end-to-end (that would need a real cluster with metrics-server, which EKS
has available as an add-on).

### Why Kustomize instead of just editing the manifests

Editing `deployment.yaml`'s image field directly for local testing, then
remembering to change it back before it could ever go to a real cluster,
is exactly the kind of manual step that gets forgotten. An overlay makes
"local" and "real" two explicit, permanent targets instead of one file
that's either right or wrong depending on who touched it last.
