import scipy.io as spio


class MatFileLoader:

    @staticmethod
    def loadmat(filename, variable_names=None):
        '''
        this function should be called instead of direct spio.loadmat
        as it cures the problem of not properly recovering python dictionaries
        from mat files. It calls the function check keys to cure all entries
        which are still mat-objects
        '''
        data = spio.loadmat(filename, struct_as_record=False,
                            squeeze_me=True, variable_names=variable_names)
        return MatFileLoader._check_keys(data)

    @staticmethod
    def _check_keys(outDict):
        '''
        checks if entries in dictionary are mat-objects. If yes
        todict is called to change them to nested dictionaries
        '''
        for key in outDict:
            if isinstance(outDict[key], spio.matlab.mio5_params.mat_struct):
                outDict[key] = MatFileLoader._todict(outDict[key])
        return outDict

    @staticmethod
    def _todict(matobj):
        '''
        A recursive function which constructs from matobjects nested dictionaries
        '''
        outDict = {}
        for strg in matobj._fieldnames:
            elem = matobj.__dict__[strg]
            if isinstance(elem, spio.matlab.mio5_params.mat_struct):
                outDict[strg] = MatFileLoader._todict(elem)
            else:
                outDict[strg] = elem
        return outDict
