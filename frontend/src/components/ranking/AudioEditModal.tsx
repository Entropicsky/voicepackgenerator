import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Button, Loader, Alert, Group, Text } from '@mantine/core';
import { IconAlertCircle, IconCrop, IconPlayerPlay, IconPlayerPause } from '@tabler/icons-react';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin, { Region } from 'wavesurfer.js/dist/plugins/regions.js';
import { Take, BatchMetadata } from '../../types';
import { api } from '../../api';

interface AudioEditModalProps {
  take: Take | null;
  batchMetadata: BatchMetadata | null;
  onCropStarted: (taskId: string) => void;
}

const AudioEditModal: React.FC<AudioEditModalProps> = ({ 
    take, 
    batchMetadata, 
    onCropStarted
}) => {
  console.log(`[AudioEditModal] Rendering inline. take: ${take?.file}`); 
  
  const waveformRef = useRef<HTMLDivElement>(null);
  const wavesurfer = useRef<WaveSurfer | null>(null);
  const activeRegion = useRef<Region | null>(null); 
  const initTimeoutRef = useRef<NodeJS.Timeout | null>(null); 

  const [isLoadingAudio, setIsLoadingAudio] = useState<boolean>(true); // Start loading
  const [isProcessingCrop, setIsProcessingCrop] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedStartTime, setSelectedStartTime] = useState<number>(0);
  const [selectedEndTime, setSelectedEndTime] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [duration, setDuration] = useState<number>(0);

  const formatTime = (time: number): string => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    const milliseconds = Math.floor((time % 1) * 1000);
    return `${minutes}:${seconds.toString().padStart(2, '0')}.${milliseconds.toString().padStart(3, '0')}`;
  };

  useEffect(() => {
    console.log(`[AudioEditModal InitEffect] Running. take: ${take?.file}, ws_current: ${!!wavesurfer.current}`);
    
    if (wavesurfer.current) {
        wavesurfer.current.destroy();
        wavesurfer.current = null;
    }
    if (initTimeoutRef.current) {
        clearTimeout(initTimeoutRef.current);
        initTimeoutRef.current = null;
    }

    if (take && batchMetadata && waveformRef.current) {
      console.log("[AudioEditModal InitEffect] Scheduling WaveSurfer initialization...");
      setIsLoadingAudio(true); 
      setIsPlaying(false);
      setDuration(0);
      setSelectedStartTime(0);
      setSelectedEndTime(0);
      activeRegion.current = null;

      initTimeoutRef.current = setTimeout(async () => {
          if (!waveformRef.current || !take || !batchMetadata) {
              console.log("[AudioEditModal Timeout] Ref/props invalid inside timeout.")
              return;
          }
          try {
              const r2Key = `${batchMetadata.skin_name}/${batchMetadata.voice_name}/${batchMetadata.batch_id}/takes/${take.file}`;
              const audioUrl = api.getAudioUrl(r2Key);
              const response = await fetch(audioUrl);
              if (!response.ok) throw new Error(`Fetch failed: ${response.statusText}`);
              const audioBlob = await response.blob();
              
              let wsInstance = WaveSurfer.create({
                container: waveformRef.current, 
                waveColor: 'rgb(200, 200, 200)', 
                progressColor: 'rgb(100, 100, 100)',
                height: 100,
                barWidth: 2,
                barGap: 1,
              });
              if (wsInstance) {
                  console.log("[AudioEditModal Timeout] Registering Regions plugin...");
                  const wsRegions = wsInstance.registerPlugin(RegionsPlugin.create());
                  console.log("[AudioEditModal Timeout] After Regions plugin registered.");

                  wsInstance.loadBlob(audioBlob);
                  wsInstance.on('ready', () => {
                      try {
                          console.log('[AudioEditModal ReadyEvent] Fired.');
                          if (!wavesurfer.current) return; 
                          setIsLoadingAudio(false);
                          const dur = wavesurfer.current.getDuration();
                          console.log(`[AudioEditModal ReadyEvent] Duration: ${dur}`);
                          setDuration(dur);
                          setSelectedEndTime(dur);
                          console.log('[AudioEditModal ReadyEvent] Adding initial region...');
                          if (wsRegions) { 
                              wsRegions.addRegion({ start: 0, end: dur, color: 'rgba(0, 100, 255, 0.1)', drag: true, resize: true });
                              console.log('[AudioEditModal ReadyEvent] Initial region added.');
                          } else {
                              console.warn('[AudioEditModal ReadyEvent] wsRegions not available to add initial region.');
                          }
                      } catch (readyErr: any) {
                         // ... error handling ...
                      }
                  });
                  wsInstance.on('error', (err) => { /* ... */ });
                  wsInstance.on('finish', () => { setIsPlaying(false); });
                  wsInstance.on('pause', () => { setIsPlaying(false); });
                  wsInstance.on('play', () => { setIsPlaying(true); });
                 
                  wsRegions.on('region-created', (region) => { 
                      try {
                         console.log('[AudioEditModal RegionCreated] Fired:', region);
                         activeRegion.current = region; 
                         setSelectedStartTime(region.start);
                         setSelectedEndTime(region.end);
                      } catch (regionErr: any) { /* ... */ }
                   });
                  wsRegions.on('region-updated', (region) => {
                        console.log("[AudioEditModal RegionUpdated] Fired:", region.start, region.end);
                        setSelectedStartTime(region.start);
                        setSelectedEndTime(region.end);
                  });
                 
                  wavesurfer.current = wsInstance;
                  console.log("[AudioEditModal Timeout] WaveSurfer instance assigned to ref (Regions Enabled).");
              } else {
                  throw new Error("WaveSurfer.create failed");
              }
          } catch (initError: any) {
              console.error("[AudioEditModal Timeout] Init Error:", initError);
              setError(`Failed to init editor: ${initError.message}`);
              setIsLoadingAudio(false);
          }
      }, 0); 
    }

    return () => {
        if (initTimeoutRef.current) clearTimeout(initTimeoutRef.current);
        if (wavesurfer.current) {
            console.log(`[AudioEditModal Cleanup] Destroying WS for ${take?.file}`);
            wavesurfer.current.destroy();
            wavesurfer.current = null;
        }
    };
    
  }, [take, batchMetadata]);

  const handlePlayPause = useCallback(() => {
      if (!wavesurfer.current) {
          console.warn("Play/Pause clicked but wavesurfer not ready.");
          return;
      }
      if (isPlaying) {
          wavesurfer.current.pause();
      } else {
         if (activeRegion.current) {
             console.log(`Playing region: ${activeRegion.current.start} to ${activeRegion.current.end}`);
             wavesurfer.current.play(activeRegion.current.start, activeRegion.current.end);
         } else {
             console.warn("No active region found, playing full track.");
             wavesurfer.current.play();
         }
      }
  }, [isPlaying]);

  const handleSaveCrop = useCallback(async () => {
    if (!take || !batchMetadata || !activeRegion.current || selectedStartTime === null || selectedEndTime === null || selectedStartTime >= selectedEndTime) {
      setError("Invalid selection. Please select a valid start and end time using the region handles.");
      return;
    }

    setIsProcessingCrop(true);
    setError(null);
    
    const startTime = activeRegion.current.start;
    const endTime = activeRegion.current.end;

    const batchPrefix = `${batchMetadata.skin_name}/${batchMetadata.voice_name}/${batchMetadata.batch_id}`;
    const filename = take.file;

    console.log(`Saving crop for ${filename}: Start ${startTime}, End ${endTime}`);

    try {
       const result = await api.cropTake(batchPrefix, filename, startTime, endTime);
       console.log("Crop task started via API:", result);
       
       setIsProcessingCrop(false);
       setError(null);
       onCropStarted(result.task_id);

    } catch (err: any) {
      console.error("Crop failed:", err);
      setError(`Crop failed: ${err.message || 'Unknown error'}`);
      setIsProcessingCrop(false);
    }
  }, [take, batchMetadata, selectedStartTime, selectedEndTime, onCropStarted]);

  return (
    <>
      {error && (
        <Alert icon={<IconAlertCircle size="1rem" />} title="Error" color="red" mb="md">
          {error}
        </Alert>
      )}

      {take ? (
        <>
           <div ref={waveformRef} style={{ border: '1px solid #ccc', marginBottom: '15px', minHeight: '102px' }}>
             {isLoadingAudio && (
               <Group justify="center" style={{ height: '100px', alignItems: 'center' }}>
                 <Loader />
                 <Text>Loading audio waveform...</Text>
               </Group>
             )}
           </div>
           <Group justify="space-between" mb="md">
                 <Button 
                     onClick={handlePlayPause} 
                     leftSection={isPlaying ? <IconPlayerPause size={16} /> : <IconPlayerPlay size={16} />}
                     disabled={isLoadingAudio}
                 >
                     {isPlaying ? 'Pause Preview' : 'Play Selection'}
                 </Button>
               <Text size="sm">
                 Selection: {formatTime(selectedStartTime)} - {formatTime(selectedEndTime)} (Duration: {formatTime(selectedEndTime - selectedStartTime)}) | Total: {formatTime(duration)}
               </Text>
           </Group>
           <Group justify="flex-end">
             <Button onClick={handleSaveCrop} 
               leftSection={<IconCrop size={16} />} 
               loading={isProcessingCrop} 
               disabled={isLoadingAudio || selectedStartTime === null || selectedEndTime === null || selectedStartTime >= selectedEndTime}
             >
               Save Crop
             </Button>
           </Group> 
        </>
      ) : (
        <Text>No take data provided.</Text> 
      )}
    </>
  );
};

export default AudioEditModal; 