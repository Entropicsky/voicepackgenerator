Based on the guidelines below, write this in the perfect way to get a good voice generation out of Elevenlabs for this video game voice line, appropriately expressing pace and emotion. IMPORTANT: RESPOND WITH ONLY THE TEXT-TO-SPEECH PROMPT AND NO OTHER EXPLANATION OR FLUFF. 

[INSERT LINE HERE]

ElevenLabs rules:

Here are the concise, actionable **key rules** for prompting ElevenLabs Text-to-Speech, optimized for an LLM agent writing voice lines:

### ElevenLabs Prompt-Writing Rules:

**1. Punctuation & Pauses**
- Use commas ,, ellipses ..., and dashes — to control rhythm and pauses naturally.  
- ALSO: For more precise pause control, use SSML <break> tags, as follows:  
  *(e.g., "It's now or never.<break time='0.5s'/>Move!")*
- NOTE: These break tags and punctuation are often the most impactful changes to the direction, so be sure to use these where you think appropriate. 

**2. Emotion & Context**
- If needed, Clearly specify emotional context directly in prompt:  
  *(e.g., "angrily," "nervously," "excitedly")*
- Add brief emotional/narrative padding around key dialogue if needed; remove in audio editing later:  
  *(e.g., "He roars fiercely, 'Attack!'")*
- Never put these in the middle of a prompt. Only at the beginning  
- Only add this if you feel it will be needed. 

**3. Pronunciation**
- Spell difficult names or terms phonetically or use hyphens and capitalization clearly:  
  *(e.g., "Xbalanque" → "Shib-a-lan-kay")*
- Prefer SSML phoneme tags (IPA or ARPAbet) for accurate pronunciation:  
  *(e.g., <phoneme alphabet="ipa" ph="ˈʃɪbəˌlɑːŋkeɪ">Xbalanque</phoneme>)*

**4. Emphasis**
- Capitalize or punctuate words needing strong emphasis or shouting:  
  *(e.g., "FIRE!", "STOP!")*
- Use SSML <emphasis> tags for subtle emphasis on important words if supported:  
  *(e.g., "We need <emphasis>backup</emphasis> now!")*

**5. Prompt Style Consistency**
- Write prompts in the character's voice and personality style consistently.  
- Match writing style (formal, slang, humor) clearly to the character's established tone.

**7. Length & Clarity**
- Keep prompts clear, direct, and short; long prompts should be segmented clearly with punctuation or breaks.  
- Avoid overly complex or confusing phrasing that might disrupt smooth delivery.
- Feel free to change the voice line slightly if you think the change could make it easier for the text-to-speech engine to work well, as long as it mostly preserves the purpose/meaning of the line.  

**8. Phonetic sounds for bracketed items**
- If a term is bracketed inside a quote that obviously implies a certain type of phoentic sound, thentry to replace it with a phonetic sound. If helpful, use SSML phoneme tags (IPA or ARPAbet) for accurate pronunciation 
- Example [dog sound] = "OOOF OFFF"


### Example Agent Prompt:
> *(excitedly)* "That's another kill! Let's keep it up!"  
> *(hesitantly)* "I... I'm not sure about this."  
> *(shouting urgently)* "Defend the titan NOW!"
> "It's now or never.<break time='0.5s'/>Move!"
> "We need to regroup<break time='0.3s'/> and plan our next attack."
> (frantically)* "The enemy is approaching from the left flank.<break time='0.7s'/> PREPARE YOURSELVES!"

These concise rules ensure high-quality, consistent, and contextually rich voice outputs optimized specifically for use in SMITE 2 voice line generation. 