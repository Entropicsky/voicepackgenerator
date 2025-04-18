import React from 'react';
import { useParams } from 'react-router-dom';
import ScriptEditor from '../components/scripts/ScriptEditor';

const ScriptEditorPage: React.FC = () => {
  const { scriptId: scriptIdParam } = useParams<{ scriptId: string }>();
  const scriptId = scriptIdParam ? parseInt(scriptIdParam, 10) : undefined;

  if (scriptIdParam && isNaN(scriptId!)) {
      return <p>Error: Invalid Script ID provided in URL.</p>;
  }

  return (
    <div>
      <ScriptEditor scriptId={scriptId} />
    </div>
  );
};

export default ScriptEditorPage; 