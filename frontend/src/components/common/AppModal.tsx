import React from 'react';
import { Modal, ModalProps } from '@mantine/core';

// Extend ModalProps to accept children explicitly if needed, 
// though ModalProps often includes it or relies on component structure.
interface AppModalProps extends Omit<ModalProps, 'closeOnClickOutside'> {
  // Add any custom props for AppModal here if needed in the future
}

const AppModal: React.FC<AppModalProps> = (props) => {
  // Define the centering styles
  const centeringStyles = {
      inner: {
        // Use calc to attempt slight offset if needed, adjust as necessary
        left: 'calc(50% + 0px)', // Adjust 0px offset if needed
        transform: 'translateX(-50%)',
      },
  };
  
  // Merge existing styles prop with our centering styles
  // Prioritize centering styles by putting them last in the merge
  const mergedStyles = props.styles 
    ? { ...props.styles, ...centeringStyles } 
    : centeringStyles;

  // Spread all received props, enforce closeOnClickOutside={false}, and apply merged styles
  return <Modal {...props} closeOnClickOutside={false} styles={mergedStyles} />;
};

export default AppModal; 