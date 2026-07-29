# Prerequisites

## Required Resources
- an existing git provider repository with the target project/release data — either a GitLab project (`git_provider.type = gitlab`) or an Alibaba Cloud Codeup repository (`git_provider.type = codeup`)
- an existing ACR instance and namespace if image-related entities are expected
- an existing ACK deployment or pods if k8s/image relationships are expected
- an existing CMS workspace
- a config directory containing `app_config.yaml` and related mapping files

## Required Repository Files
- `devops_data_generator/config/app_config.yaml`
- `devops_data_generator/config/data_mapping.yaml`
- `devops_data_generator/config/repo_image_mapping.yaml`
- `devops_data_generator/config/static_topo.yaml`

## Required Runtime Inputs
- Git provider credentials when git tasks are expected to run:
  - GitLab personal access token (when `git_provider.type = gitlab`), or
  - Alibaba Cloud RAM access key id/secret + Codeup organization id (when `git_provider.type = codeup`)
- Alibaba Cloud credentials for CMS/SLS/ACR paths when those tasks are expected to run
- kubeconfig or CMS pod source configuration if pod-related checks are expected

## Explicit Non-Assumptions
- first-wave skills do not create the CMS workspace
- first-wave skills do not create git provider repositories (GitLab or Codeup)
- first-wave skills do not create ACR namespaces or registries
- first-wave skills do not deploy the application to ACK

## Blocked Conditions
Return `blocked` when:
- the CMS workspace does not exist
- required repo/config files are missing
- the expected external resource for the requested stage does not exist
