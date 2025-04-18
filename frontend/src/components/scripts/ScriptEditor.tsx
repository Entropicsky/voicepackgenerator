import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { ScriptLineCreateOrUpdate, ScriptMetadata } from '../../types';
import { Button, TextInput, Textarea, Loader, Alert, Group, ActionIcon, Table, Text, FileButton, Tooltip, Stack } from '@mantine/core';
import { IconAlertCircle, IconTrash, IconArrowUp, IconArrowDown, IconPlus, IconUpload, IconDownload, IconDeviceFloppy, IconPlayerPause } from '@tabler/icons-react';
import Papa from 'papaparse';
// Consider using react-dropzone for CSV import later?
// Consider using a library like react-beautiful-dnd for drag/drop reordering later?

interface ScriptEditorProps {
  scriptId?: number; // If undefined, we are creating a new script
}

const ScriptEditor: React.FC<ScriptEditorProps> = ({ scriptId }) => {
  const navigate = useNavigate();
  const isNew = scriptId === undefined;
  const resetRef = useRef<() => void>(null); // Ref for FileButton reset function
  const lineTextareaRefs = useRef<(HTMLTextAreaElement | null)[]>([]); // Refs for textareas

  // Form State
  const [name, setName] = useState<string>('');
  const [description, setDescription] = useState<string>('');
  const [lines, setLines] = useState<ScriptLineCreateOrUpdate[]>([]);

  // UI State
  const [loading, setLoading] = useState<boolean>(!isNew); // Only load if editing
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [importing, setImporting] = useState<boolean>(false);

  // Ensure refs array has the correct size
  useEffect(() => {
    lineTextareaRefs.current = lineTextareaRefs.current.slice(0, lines.length);
  }, [lines.length]);

  // Fetch data for existing script
  useEffect(() => {
    if (!isNew && scriptId) {
      setLoading(true);
      setError(null);
      api.getScriptDetails(scriptId)
        .then(script => {
          setName(script.name);
          setDescription(script.description || '');
          // Map ScriptLine to ScriptLineCreateOrUpdate (omit id, script_id)
          setLines(script.lines.map(line => ({
            line_key: line.line_key,
            text: line.text,
            order_index: line.order_index
          })));
        })
        .catch(err => {
          console.error("Error fetching script details:", err);
          setError(`Failed to load script details: ${err.message}`);
        })
        .finally(() => setLoading(false));
    }
  }, [scriptId, isNew]);

  // --- Line Management Handlers ---
  const handleLineChange = (index: number, field: 'line_key' | 'text', value: string) => {
    setLines(currentLines => 
      currentLines.map((line, i) => 
        i === index ? { ...line, [field]: value } : line
      )
    );
  };

  const handleAddLine = () => {
    setLines(currentLines => [
      ...currentLines,
      { line_key: `NEW_KEY_${currentLines.length + 1}`, text: '', order_index: currentLines.length }
    ]);
    // Simple re-indexing after add
    reindexLines();
  };

  const handleRemoveLine = (indexToRemove: number) => {
    setLines(currentLines => currentLines.filter((_, i) => i !== indexToRemove));
    // Simple re-indexing after remove
    reindexLines(); 
  };

  const moveLine = (index: number, direction: 'up' | 'down') => {
    setLines(currentLines => {
      const newLines = [...currentLines];
      const targetIndex = direction === 'up' ? index - 1 : index + 1;

      if (targetIndex < 0 || targetIndex >= newLines.length) {
        return newLines; // Cannot move outside bounds
      }

      // Swap elements
      [newLines[index], newLines[targetIndex]] = [newLines[targetIndex], newLines[index]];
      
      // Re-index all lines after move to ensure sequential order_index
      return newLines.map((line, idx) => ({ ...line, order_index: idx }));
    });
  };
  
  // Helper to ensure order_index is sequential starting from 0
  const reindexLines = () => {
      setLines(currentLines => 
          currentLines.map((line, idx) => ({ ...line, order_index: idx }))
      );
  };

  // Ensure lines are re-indexed whenever the array potentially changes order/length
  useEffect(() => {
      reindexLines();
  }, [lines.length]); // Re-index if lines are added/removed

  // --- Save Handler ---
  const handleSave = async () => {
    setError(null);
    setSaving(true);

    // Validate name
    if (!name.trim()) {
        setError("Script name cannot be empty.");
        setSaving(false);
        return;
    }
    
    // Validate line keys (basic check for emptiness and duplicates)
    const seenKeys = new Set<string>();
    for (let i = 0; i < lines.length; i++) {
        const key = lines[i].line_key.trim();
        if (!key) {
            setError(`Line ${i + 1} has an empty key.`);
            setSaving(false);
            return;
        }
        if (seenKeys.has(key)) {
             setError(`Duplicate line key "${key}" found at line ${i + 1}. Keys must be unique within a script.`);
             setSaving(false);
             return;
        }
        seenKeys.add(key);
    }

    // Ensure lines have sequential order_index (should be handled by state updates, but double check)
    const finalPayloadLines = lines.map((line, idx) => ({ ...line, order_index: idx }));

    try {
      // --- Adjustments for Create vs Update --- 
      if (isNew) {
        // ADJUSTED LOGIC FOR CREATE:
        const createPayload = { name: name.trim(), description: description.trim() || null };
        let createdScriptMeta: ScriptMetadata | null = null; 
        
        try {
            createdScriptMeta = await api.createScript(createPayload);
            console.log("Created script metadata:", createdScriptMeta);

            // If lines were added in the form *before* first save, try to update immediately
            if (finalPayloadLines.length > 0 && createdScriptMeta) {
                console.log(`Attempting to update new script ${createdScriptMeta.id} with ${finalPayloadLines.length} lines.`);
                const updatePayload = { lines: finalPayloadLines }; // payloadLines created earlier
                
                // Nested try-catch for the line update
                try {
                    await api.updateScript(createdScriptMeta.id, updatePayload);
                    console.log("Updated new script with initial lines.");
                    // Success: Both metadata and lines saved
                    alert(`Script "${createdScriptMeta.name}" created successfully!`);
                    navigate(`/scripts/${createdScriptMeta.id}`); // Navigate only after everything succeeds
                } catch (updateErr: any) {
                    console.error(`Error updating script ${createdScriptMeta.id} with lines:`, updateErr);
                    // Set error but keep form data - metadata exists, lines failed
                    setError(`Script metadata saved, but failed to save lines: ${updateErr.message}. You can try saving again.`);
                    // Do not navigate here
                }
            } else if (createdScriptMeta) {
                // No lines to add, metadata creation was successful
                alert(`Script "${createdScriptMeta.name}" created successfully!`);
                navigate(`/scripts/${createdScriptMeta.id}`); // Navigate after metadata creation
            }

        } catch (createErr: any) {
            console.error("Error creating script metadata:", createErr);
            // Handle specific create errors (like duplicate name) or generic ones
            if (createErr.message?.includes('already exists')) {
                setError(`Script name "${name.trim()}" already exists. Please choose a different name.`);
            } else {
                setError(`Failed to create script: ${createErr.message}`);
            }
            // Keep form data populated, do not navigate
        }

      } else if (scriptId) {
        // Existing update logic: Update metadata and lines together
        const updatePayload = {
            name: name.trim(),
            description: description.trim() || null,
            lines: finalPayloadLines,
        };
        // Outer try-catch handles errors for the update operation
        const savedScript = await api.updateScript(scriptId, updatePayload);
        alert(`Script "${savedScript.name}" updated successfully!`);
        // Stay on the page after saving an existing script?
        // navigate(`/scripts`); // Optionally navigate back to list
      }
    } catch (err: any) {
      // This outer catch will now primarily catch errors from the UPDATE logic for existing scripts,
      // or potentially unexpected errors if the isNew/scriptId logic is flawed.
      // Errors during CREATE are handled within the nested try-catch blocks.
      console.error("Unhandled error during save operation:", err);
      setError(`An unexpected error occurred: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  // --- NEW: CSV Handlers ---
  const handleImportCsv = (file: File | null) => {
    if (!file) return;
    setError(null);
    setImporting(true);

    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: async (results) => {
        setImporting(false); // Set importing false early in case of errors below
        resetRef.current?.(); // Reset file input regardless of outcome below

        const { data, errors, meta } = results;

        if (errors.length > 0 || !meta.fields || !meta.fields.includes('line_key') || !meta.fields.includes('text')) {
            setError(errors.length > 0 ? `Error parsing CSV: ${errors[0].message} on row ${errors[0].row}` : "CSV must contain 'line_key' and 'text' columns.");
            return; // Stop processing
        }

        try {
            // --- Process CSV data --- 
            const linesByKey = new Map<string, ScriptLineCreateOrUpdate>();
            // Use current state lines as the base for merging
            lines.forEach(line => linesByKey.set(line.line_key, line)); 

            data.forEach((row: any, index) => {
                const lineKey = row.line_key?.trim();
                const text = row.text?.trim() ?? '';
                if (!lineKey) {
                    console.warn(`Skipping CSV row ${index + 1} due to missing or empty 'line_key'.`);
                    return;
                }
                const existingLine = linesByKey.get(lineKey);
                if (existingLine) {
                    linesByKey.set(lineKey, { ...existingLine, text: text });
                } else {
                    linesByKey.set(lineKey, { line_key: lineKey, text: text, order_index: -1 });
                }
            });
            const processedLines = Array.from(linesByKey.values()).map((line, idx) => ({ ...line, order_index: idx }));

            // Update state for UI reactivity
            setLines(processedLines);

            // --- Save Logic based on isNew --- 
            setSaving(true); // Indicate save operation is starting
            setError(null); // Clear previous errors

            if (isNew) {
                // **NEW SCRIPT LOGIC**: Create metadata then update with processed lines
                console.log("Importing to a NEW script. Performing create then update...");
                const createPayload = { name: name.trim(), description: description.trim() || null };
                
                if (!createPayload.name) { // Add validation check for name before API call
                     throw new Error("Script name cannot be empty.");
                }
                
                let createdScriptMeta: ScriptMetadata | null = null;
                try {
                    createdScriptMeta = await api.createScript(createPayload);
                    console.log("Created script metadata:", createdScriptMeta);

                    if (processedLines.length > 0 && createdScriptMeta) {
                        console.log(`Attempting to update new script ${createdScriptMeta.id} with ${processedLines.length} lines.`);
                        const updatePayload = { lines: processedLines }; // Use processedLines directly
                        try {
                            await api.updateScript(createdScriptMeta.id, updatePayload);
                            console.log("Updated new script with imported lines.");
                            alert(`Script "${createdScriptMeta.name}" created and lines imported successfully!`);
                            navigate(`/scripts/${createdScriptMeta.id}`); // Navigate on full success
                        } catch (updateErr: any) {
                            console.error(`Error updating script ${createdScriptMeta.id} with lines:`, updateErr);
                            setError(`Script metadata saved, but failed to save imported lines: ${updateErr.message}.`);
                            // Don't navigate, allow user to retry save maybe?
                        }
                    } else if (createdScriptMeta) {
                        // Metadata created, but no lines in CSV (or processing failed to produce lines? unlikely here)
                        alert(`Script "${createdScriptMeta.name}" created successfully (no lines imported).`);
                        navigate(`/scripts/${createdScriptMeta.id}`);
                    }
                } catch (createErr: any) {
                    console.error("Error creating script metadata during import:", createErr);
                    if (createErr.message?.includes('already exists')) {
                        setError(`Script name "${name.trim()}" already exists. Please choose a different name.`);
                    } else {
                        setError(`Failed to create script: ${createErr.message}`);
                    }
                     // Keep imported lines in state, but don't navigate
                }

            } else {
                // **EXISTING SCRIPT LOGIC**: Delegate to the standard save handler
                console.log("Importing to an EXISTING script. Calling handleSave...");
                // handleSave uses the latest `lines` state due to useCallback dependency
                // or because the state update from setLines(processedLines) will have rendered.
                await handleSave(); 
            }

        } catch (err: any) {
            console.error("Error during CSV processing or saving:", err);
            setError(`Operation failed: ${err.message}`);
        } finally {
             setSaving(false); // Ensure saving indicator is turned off
             // resetRef and setImporting handled earlier/outside this try
        }
      },
      error: (error: Error) => {
        setError(`Failed to parse CSV: ${error.message}`);
        setImporting(false);
        resetRef.current?.();
      }
    });
  };

  const handleExportCsv = () => {
    setError(null);
    if (lines.length === 0) {
        setError("There are no lines to export.");
        return;
    }

    try {
        // Prepare data for CSV (only key and text)
        const csvData = lines.map(line => ({
            line_key: line.line_key,
            text: line.text
        }));

        const csvString = Papa.unparse(csvData);

        // Create Blob and download link
        const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        // Use script name for filename, default if empty or new
        const scriptName = name.trim().replace(/[^a-z0-9]/gi, '_').toLowerCase() || 'new_script';
        link.setAttribute('download', `${scriptName}_lines.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

    } catch (err: any) {
        console.error("Error exporting CSV:", err);
        setError(`Failed to export CSV: ${err.message}`);
    }
  };

  // --- NEW: Insert Pause Handler ---
  const handleInsertPause = (index: number) => {
    const textarea = lineTextareaRefs.current[index];
    if (!textarea) {
        console.warn("Textarea ref not found for index:", index);
        return;
    }

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const currentValue = lines[index].text;
    const pauseSnippet = '<break time="0.5s" />';

    const newValue = 
        currentValue.substring(0, start) + 
        pauseSnippet + 
        currentValue.substring(end);

    // Update state using existing handler
    handleLineChange(index, 'text', newValue);

    // Focus the textarea and set cursor position after the inserted text
    // Needs to happen after state update potentially rerenders the textarea
    // Use a small timeout to allow React to re-render
    setTimeout(() => {
        const updatedTextarea = lineTextareaRefs.current[index];
        if (updatedTextarea) {
            updatedTextarea.focus();
            const newCursorPos = start + pauseSnippet.length;
            updatedTextarea.selectionStart = newCursorPos;
            updatedTextarea.selectionEnd = newCursorPos;
        }
    }, 0);
  };

  // --- Render --- 
  if (loading) {
    return <Loader />; 
  }

  return (
    <div>
      {error && (
        <Alert icon={<IconAlertCircle size="1rem" />} title="Error" color="red" withCloseButton onClose={() => setError(null)} mb="md">
          {error}
        </Alert>
      )}

      <TextInput
        label="Script Name"
        placeholder="Enter a unique name for the script"
        required
        value={name}
        onChange={(event) => setName(event.currentTarget.value)}
        mb="md"
        disabled={saving}
      />

      <Textarea
        label="Description (Optional)"
        placeholder="Enter a brief description of the script"
        value={description}
        onChange={(event) => setDescription(event.currentTarget.value)}
        mb="md"
        autosize
        minRows={2}
        disabled={saving}
      />
      
      <Text fw={500} size="sm" mb="xs">Script Lines</Text>
      <Table withTableBorder withColumnBorders mb="md">
          <Table.Thead>
              <Table.Tr>
                  <Table.Th style={{ width: '40px' }}>#</Table.Th>
                  <Table.Th style={{ width: '50px' }}>Order</Table.Th>
                  <Table.Th style={{ width: '200px' }}>Line Key</Table.Th>
                  <Table.Th>Line Text</Table.Th>
                  <Table.Th style={{ width: '50px' }}>Save</Table.Th>
                  <Table.Th style={{ width: '50px' }}>Del</Table.Th>
              </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
              {lines.map((line, index) => (
                  <Table.Tr key={`${line.line_key}-${index}`}>
                      <Table.Td>{index + 1}</Table.Td>
                      <Table.Td>
                          <Group gap="xs" wrap="nowrap">
                              <ActionIcon 
                                size="sm" 
                                variant="outline" 
                                onClick={() => moveLine(index, 'up')} 
                                disabled={index === 0 || saving}
                              >
                                  <IconArrowUp size={14} />
                              </ActionIcon>
                              <ActionIcon 
                                size="sm" 
                                variant="outline" 
                                onClick={() => moveLine(index, 'down')} 
                                disabled={index === lines.length - 1 || saving}
                              >
                                  <IconArrowDown size={14} />
                              </ActionIcon>
                          </Group>
                      </Table.Td>
                      <Table.Td>
                          <TextInput
                              value={line.line_key}
                              onChange={(e) => handleLineChange(index, 'line_key', e.currentTarget.value)}
                              placeholder="Unique Line Key"
                              required
                              disabled={saving}
                              error={!line.line_key.trim()} // Basic validation feedback
                          />
                      </Table.Td>
                      <Table.Td>
                          <Stack gap="xs">
                              <Textarea
                                  ref={(el) => { lineTextareaRefs.current[index] = el; }} 
                                  value={line.text}
                                  onChange={(e) => handleLineChange(index, 'text', e.currentTarget.value)}
                                  placeholder="Text for the voice to speak..."
                                  autosize
                                  minRows={1}
                                  required
                                  disabled={saving || importing}
                              />
                              <Tooltip label="Insert 0.5s Pause at Cursor">
                                  <ActionIcon 
                                      variant="default" 
                                      size="xs" 
                                      onClick={() => handleInsertPause(index)}
                                      disabled={saving || importing}
                                      style={{ alignSelf: 'flex-start' }}
                                  >
                                      <IconPlayerPause size={14} />
                                  </ActionIcon>
                              </Tooltip>
                          </Stack>
                      </Table.Td>
                      <Table.Td>
                          <ActionIcon
                              variant="outline"
                              color="blue"
                              onClick={handleSave}
                              disabled={saving || importing}
                              title="Save Script Changes"
                          >
                              <IconDeviceFloppy size={14} />
                          </ActionIcon>
                      </Table.Td>
                      <Table.Td>
                          <ActionIcon
                              color="red"
                              variant="outline"
                              onClick={() => handleRemoveLine(index)}
                              disabled={saving || importing}
                          >
                              <IconTrash size={14} />
                          </ActionIcon>
                      </Table.Td>
                  </Table.Tr>
              ))}
          </Table.Tbody>
      </Table>
      
      <Group mb="md">
          <Button
            leftSection={<IconPlus size={14}/>}
            onClick={handleAddLine}
            variant="outline"
            size="xs"
            disabled={saving || importing}
          >
              Add Line
          </Button>
          <FileButton onChange={handleImportCsv} accept="text/csv" resetRef={resetRef}>
              {(props) => (
                  <Button
                      {...props} 
                      leftSection={<IconUpload size={14}/>}
                      variant="outline"
                      size="xs"
                      loading={importing}
                      disabled={saving || importing}
                  >
                      Import CSV
                  </Button>
              )}
          </FileButton>
          <Button
            leftSection={<IconDownload size={14}/>}
            onClick={handleExportCsv}
            variant="outline"
            size="xs"
            disabled={saving || importing || lines.length === 0}
          >
              Export CSV
          </Button>
      </Group>

      <Group justify="flex-end" mt="lg">
        <Button onClick={() => navigate('/scripts')} variant="default" disabled={saving || importing}>
            Cancel
        </Button>
        <Button onClick={handleSave} loading={saving} disabled={!name.trim() || importing}>
            {isNew ? 'Create Script' : 'Save Changes'}
        </Button>
      </Group>
    </div>
  );
};

export default ScriptEditor; 