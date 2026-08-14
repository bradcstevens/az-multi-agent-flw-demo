import React from 'react';
import { Button } from '@fluentui/react-components';

import { StartingTask } from '../../models/Team';
import '../../styles/followOnTask.css';

interface FollowOnTaskProps {
  task: StartingTask;
  onSelect: (task: StartingTask) => void;
  disabled: boolean;
}

const FollowOnTask: React.FC<FollowOnTaskProps> = ({ task, onSelect, disabled }) => (
  <div className="follow-on-task" data-testid="follow-on-task">
    <Button appearance="outline" size="large" disabled={disabled} onClick={() => onSelect(task)}>
      {task.name}
    </Button>
  </div>
);

export default FollowOnTask;
