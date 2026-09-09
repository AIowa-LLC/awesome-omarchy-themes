name: Bug report
description: Something is broken or renders wrong in a theme
labels: ["bug"]
body:
  - type: input
    id: theme
    attributes:
      label: Theme
      description: Which theme (directory name under themes/) is affected?
      placeholder: e.g. my-theme
    validations:
      required: true
  - type: input
    id: omarchy-version
    attributes:
      label: Omarchy version
      description: Output of `omarchy version`
      placeholder: e.g. quattro
    validations:
      required: true
  - type: textarea
    id: what-happened
    attributes:
      label: What happened?
      description: A clear description of the problem. Include screenshots if it renders visually.
      placeholder: Describe what you saw and what you expected instead.
    validations:
      required: true
  - type: textarea
    id: steps
    attributes:
      label: Steps to reproduce
      placeholder: |
        1. Install the theme: cp -r themes/<name> ~/.config/omarchy/themes/
        2. Apply: omarchy theme set <name>
        3. ...
    validations:
      required: true
  - type: textarea
    id: context
    attributes:
      label: Additional context
      description: Logs, related issues, or anything else useful.
