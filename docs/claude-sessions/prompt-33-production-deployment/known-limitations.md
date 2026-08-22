# TourSafe Prompt 33 — Known Limitations

## 1. External Cloud Access in Local Workstation
- **Limitation**: Direct cloud provisioning (`terraform apply` or `kubectl apply` against live AWS/GKE clusters) requires active cloud credentials and VPC peering that are not mounted in this local development workspace.
- **Mitigation**: All Terraform blueprints, Kubernetes manifests, Dockerfiles, and CI/CD GitHub Actions workflows are fully structured, syntax-checked, and ready for deployment (`READY_FOR_DEPLOYMENT`).

## 2. Mobile App Store Distribution Credentials
- **Limitation**: Google Play Service Account JSON and Apple Developer provisioning certificates cannot be committed to Git.
- **Mitigation**: Configured `frontend/eas.json` with secure environment variable placeholders (`EXPO_PUBLIC_*`) and detailed setup instructions in `docs/deployment/mobile-build-pipeline.md`.
