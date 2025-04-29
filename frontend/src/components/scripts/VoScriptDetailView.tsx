// When rendering action buttons for a line
const renderLineActions = (line) => {
  // Check if this line comes from a static template
  const isFromStaticTemplate = line.template_line && (
    // Check if the data is loaded and the template_line has static_text
    (templateLinesMap[line.template_line_id]?.static_text)
  );
  
  return (
    <Group gap="xs">
      {/* Only show lock/unlock if not from static template */}
      {!isFromStaticTemplate && (
        <ActionIcon
          variant="subtle"
          color={line.is_locked ? "orange" : "gray"}
          onClick={() => handleToggleLock(line.id)}
          loading={toggleLockMutation.isPending && toggleLockMutation.variables === line.id}
          title={line.is_locked ? "Unlock Line" : "Lock Line"}
        >
          {line.is_locked ? <IconLock size={16} /> : <IconLockOpen size={16} />}
        </ActionIcon>
      )}

      {/* Only show refine button if not from static template */}
      {!isFromStaticTemplate && (
        <ActionIcon
          variant="subtle"
          color="blue"
          onClick={() => handleOpenRefineModal(line)}
          title="Refine Line"
        >
          <IconWand size={16} />
        </ActionIcon>
      )}

      {/* Only show regenerate button if not from static template and status is pending */}
      {!isFromStaticTemplate && line.status === 'pending' && (
        <ActionIcon
          variant="subtle"
          color="teal"
          onClick={() => handleGenerateSingleLine(line.id)}
          loading={generateLineMutation.isPending && generateLineMutation.variables === line.id}
          title="Generate Line"
        >
          <IconRefresh size={16} />
        </ActionIcon>
      )}

      {/* Edit and Delete actions are always available */}
      <ActionIcon
        variant="subtle"
        color="violet"
        onClick={() => handleUpdateText(line)}
        title="Edit Text"
      >
        <IconPencil size={16} />
      </ActionIcon>

      <ActionIcon
        variant="subtle"
        color="red"
        onClick={() => handleDeleteLine(line.id, line.line_key || `Line ${line.id}`)}
        loading={deleteLineMutation.isPending && deleteLineMutation.variables === line.id}
        title="Delete Line"
      >
        <IconTrash size={16} />
      </ActionIcon>
    </Group>
  );
};

// Modify the line render to visually distinguish static template lines
const renderLineText = (line) => {
  // Check if this line comes from a static template
  const isFromStaticTemplate = line.template_line && (
    // Check if the data is loaded and the template_line has static_text
    (templateLinesMap[line.template_line_id]?.static_text)
  );
  
  return (
    <Textarea
      value={line.generated_text || ''}
      minRows={3}
      autosize
      readOnly={true}
      styles={{
        input: {
          fontFamily: 'monospace',
          backgroundColor: isFromStaticTemplate ? '#f0f8ff' : undefined, // Light blue background for static lines
          border: isFromStaticTemplate ? '1px solid #b3d9ff' : undefined
        }
      }}
    />
  );
};

// Add a badge or indicator for static template lines
const renderLineStatus = (line) => {
  // Check if this line comes from a static template
  const isFromStaticTemplate = line.template_line && (
    // Check if the data is loaded and the template_line has static_text
    (templateLinesMap[line.template_line_id]?.static_text)
  );
  
  return (
    <Group gap="xs">
      <Badge color={getStatusColor(line.status)}>
        {line.status}
      </Badge>
      
      {isFromStaticTemplate && (
        <Badge color="blue" variant="light">
          Static Template
        </Badge>
      )}
    </Group>
  );
}; 