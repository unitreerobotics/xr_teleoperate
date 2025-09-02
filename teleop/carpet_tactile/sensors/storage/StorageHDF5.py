import sys; sys.path.insert(0, '.')
import sys, os, re, time, shutil, math, random, datetime, argparse, signal
import numpy as np
import h5py

from ..storage.Storage import Storage
from ..app.AppContext import AppContext
from ..common import dataset_tools


class StorageHDF5(Storage):
    
    # Implementation details
    def getName(self):
        return '%s (StorageHDF5)' % self.name
    
    def _init(self):

        self.blockSize = 1024
        if hasattr(self.opts, 'blockSize'):
            self.blockSize = int(self.opts.blockSize)
            self.log('Setting block size to %d.' % self.blockSize)

        # Setup output
        self.hdf5Filename = os.path.join(dataset_tools.preparePath(self.outputPath), '%s.hdf5' % self.name)
        self.log('Output file: %s' % self.hdf5Filename)
        self.f = h5py.File(self.hdf5Filename, 'w')
        self.inited = False

    def _release(self):
        # Trim unused space
        oldSize = self.f['ts'].shape[0]
        newSize = self.frameCount
        self.log('Trimming datasets from %d to %d frames...' % (oldSize, newSize))
        for k,v in self.f.items():
            if k == 'frame_count':
                continue
            self.f[k].resize(newSize, axis=0)

        # Close
        self.f.close()
        self.log('Closed HDF5 file %s.' % self.hdf5Filename)


    def _addFrame(self, ts, data):
        
        # Add ts as a standard column
        data['ts'] = int(round(ts))

        if not self.inited:
            # Initialize datasets
            self.f.create_dataset('frame_count', (1,), dtype=np.uint32)
            self.f['frame_count'][0] = 0
            #self.f.create_dataset('ts', (self.blockSize,), maxshape = (None,), dtype = np.float64)
            
            for k,v in data.items():
                if np.isscalar(v):   
                    v = np.array([v])                 
                    sz = [self.blockSize,]
                else:
                    v = np.array(v)
                    sz = [self.blockSize, *v.shape]
                maxShape = sz.copy()
                maxShape[0] = None
                self.f.create_dataset(k, tuple(sz), maxshape = tuple(maxShape), dtype = v.dtype)

            self.inited = True

        # Check size
        oldSize = self.f['ts'].shape[0]
        if oldSize == self.frameCount:            
            newSize = oldSize + self.blockSize
            self.log('Growing datasets from %d to %d frames...' % (oldSize, newSize))

            #self.f['ts'].resize(newSize, axis=0)
            for k,v in data.items():
                self.f[k].resize(newSize, axis=0)

        # Append data
        #self.f['ts'][self.frameCount] = ts
        for k,v in data.items():
            self.f[k][self.frameCount,...] = v


        # Note frame count
        self.frameCount += 1
        self.f['frame_count'][0] = self.frameCount

        # Flush to prevent data loss
        self.f.flush()


    
if __name__ == "__main__":  
    # Test code  
    storage = StorageHDF5('recordings', 'test', AppContext.create(), {})
    for i in range(1500):
        storage.addFrame(dataset_tools.getUnixTimestamp(), {'scalar': i, 'vec3': np.array([1,2,3], np.float32) * i, 'mat2d': np.ones((32,32), np.uint16) * i})
    storage.release()

    f = h5py.File('recordings/test.hdf5', 'r')
    import pdb; pdb.set_trace()