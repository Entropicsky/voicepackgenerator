# Instantiate Target Lines Feature Guide

## Overview

The "Instantiate Target Lines" feature allows you to dynamically create multiple similar lines targeting different characters, objects, or entities without having to manually create each line individually. This is especially useful for:

- Creating directed taunts for multiple characters in a game
- Generating item-specific voice lines (e.g., "I found a [item]!")
- Creating any repeating pattern of lines where only a target name changes

## How It Works

Instead of creating dozens of similar template lines that differ only by their target, you:

1. Create a single template category (e.g., "Directed Taunts")
2. When working on a specific script, use the Instantiate Target Lines feature
3. Provide a list of targets (e.g., character names) 
4. Optionally customize the line key prefix and prompt template
5. The system automatically creates and generates content for all the lines

## Step-by-Step Guide

### Prerequisites

- You must have a VO Script Template with at least one category
- You must be editing a VO Script created from that template

### Creating Target Lines

1. **Open the VO Script Detail View**
   - Navigate to the VO Scripts page
   - Click on an existing script to open it
   - You should see the script's lines organized by category

2. **Access the Instantiate Target Lines Modal**
   - Look for the purple "Instantiate Target Lines" button in the top action bar
   - Click this button to open the modal

3. **Configure Your Target Lines**
   - **Select Category**: Choose which category the new lines will belong to (e.g., "Directed Taunts")
   - **Enter Target Names**: Type or paste a list of targets (one per line)
     ```
     Zeus
     Anubis
     Athena
     Poseidon
     ```
   - **Customize Line Key Prefix** (Optional): Default is "DIRECTED_TAUNT_" which results in keys like "DIRECTED_TAUNT_ZEUS"
   - **Customize Prompt Template** (Optional): Default is "Line targeting {TargetName}" 
     - Example custom prompt: "Write a taunt directed at {TargetName}. Make it witty and reference their godly powers."
     - The {TargetName} placeholder will be replaced with each target name

4. **Create and Generate Lines**
   - Click the "Generate Pending Lines" button
   - The system will:
     1. Create a new line for each target in your list
     2. Assign them to the selected category
     3. Automatically trigger content generation for all new lines
   - You'll see a notification indicating that lines are being generated

5. **Review Generated Lines**
   - The page will refresh to display your newly created lines
   - Each line will be populated with AI-generated content targeting the specific entity
   - You can further refine any line by using the standard line editing tools

## Example Use Cases

### Directed Taunts in MOBAs/Fighting Games

Perfect for games with large character rosters where you want character-specific taunts:

```
Target names:
Zeus
Poseidon
Athena
Ares
Aphrodite
```

Prompt template:
```
Write a taunt that {CharacterName} would say when taunting {TargetName}. Reference {TargetName}'s abilities or personality traits in a witty way.
```

### Item Discovery in RPGs

For generating varied reactions to finding different items:

```
Target names:
Health Potion
Legendary Sword
Ancient Scroll
Gold Coins
Dragon Scale
```

Prompt template:
```
Write a short excited voice line about finding a {TargetName}. Character should express enthusiasm appropriate to the item's value.
```

### NPC Greetings

For generating greetings directed at different NPCs:

```
Target names:
Shopkeeper
Blacksmith
Innkeeper
Guard Captain
Court Wizard
```

Prompt template:
```
Write a friendly greeting that the player character would say when approaching a {TargetName} in a medieval fantasy setting.
```

## Tips and Best Practices

- **Batch Size**: While you can create many lines at once, consider limiting batches to 10-20 targets for better generation quality
- **Descriptive Prompts**: The more context you provide in your prompt template, the better the results
- **Line Key Prefixes**: Use a consistent naming scheme for line keys to keep your project organized
- **Category Organization**: Create dedicated categories for target-specific lines to keep your script organized
- **Post-Generation Editing**: Review and refine the generated content as needed

## Troubleshooting

- **Lines Created But Not Generated**: Check the browser console for any errors. Try manually refreshing the page and using the "Generate Category" button.
- **Missing Category**: Make sure you've selected a valid category that exists in the template.
- **Duplicate Line Keys**: If you try to instantiate lines with target names that already exist, those lines will be skipped.

## Technical Details

- New lines are created with `status='pending'` and no initial text
- The backend automatically triggers content generation after line creation
- Line keys are sanitized to remove special characters and convert to uppercase
- Prompt hints can include multiple placeholders with the target name 