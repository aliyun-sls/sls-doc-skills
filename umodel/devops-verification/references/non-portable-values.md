# Non-Portable Values

## Do Not Hardcode In Shared Skills
- GitLab personal access tokens
- Alibaba Cloud Codeup organization ids
- Alibaba Cloud access keys and secrets
- CMS workspace names
- SLS project names
- ACR instance ids
- ACR registry ids
- ACK cluster ids
- kubeconfig contents
- environment-specific repo-to-registry mapping values

## Portable Rules That Can Be Shared
- config comes from `app_config.yaml` and mapping files
- refresh happens before visibility and diagnosis
- missing workspace means `blocked`
- reference docs are skill assets under `.agents/skills/devops-verification/references/`, not Python runtime package assets
- the `devops-verification` skill depends on `references/` instead of copying it

## Environment-Specific But Expected Inputs
These values are legitimate inputs, but they remain environment-specific:
- `cms.workspace`
- `sls.project`
- `repo_image_mapping.yaml` actual mapping rows
- `kubernetes.cluster_id`
