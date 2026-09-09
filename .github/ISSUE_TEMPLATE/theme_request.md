name: Theme request
description: Propose a new theme or palette improvement
labels: ["enhancement"]
body:
  - type: textarea
    id: description
    attributes:
      label: What theme or change would you like?
      description: Palette inspiration (an image, another editor's scheme, a mood), target mode (dark/light), and any must-have colors.
    validations:
      required: true
  - type: textarea
    id: background
    attributes:
      label: Background images (optional)
      description: If you have source images in mind, link them and note their license. Only images we can redistribute can be committed.
