# -*- coding: utf-8 -*-
'''
@author: Hung-Hsin Chen
@mail: chenhh@par.cse.nsysu.edu.tw
'''
import os
import sys
import platform
import subprocess
import time
from cStringIO import StringIO
import numpy as np  
import pandas as pd
import scipy as sp
import scipy.stats as spstats
from datetime import (date, timedelta)

FileDir = os.path.abspath(os.path.curdir)
PklBasicFeaturesDir = os.path.join(FileDir,'pkl', 'BasicFeatures')
if platform.uname()[0] == 'Linux':
    ExpResultsDir =  os.path.join('/', 'home', 'chenhh' , 'Dropbox', 
                                  'financial_experiment', 'PySPPortfolio')
elif platform.uname()[0] =='Windows':
    ExpResultsDir= os.path.join('C:\\', 'Dropbox', 'financial_experiment', 
                                'MOGEP', 'PySPPortfolio')    
    

def constructModelMtx(symbols, startDate, endDate, money, hist_day):
    '''
    -注意因為最後一期只結算不買賣
    -DataFrame以Date取資料時，有包含last day, 即df[startDate: endDate]
    -包含了endDate的資料，但是使用index取資料時，如df[2:10]，則不包含df.ix[10]的資料
    @param symbols, list
    @param startDate, endDate, datetime.date
    @param momey, positive float
    @param hist_day, positive integer
    
    dataFrame取單一row用df.ix[idx]
    df.index.get_loc(startDate)找index所在位置
    @return riskyRetMtx, numpy.array, size: (n_rv * hist_day+T+1)
    '''
    buyTransFee, sellTransFee = 0.003, 0.004425
    
    #read data
    dfs = []
    transDates = None
    for symbol in symbols:
        df = pd.read_pickle(os.path.join(PklBasicFeaturesDir, 
                                    'BasicFeatures_%s_00-12.pkl'%symbol))
        tmp = df[startDate: endDate]
        startIdx, endIdx = df.index.get_loc(tmp.index[0]), df.index.get_loc(tmp.index[-1])
        if startIdx < hist_day:
            raise ValueError('%s do not have enough data'%(symbol))
        data = df[startIdx-hist_day: endIdx+1]
        print data['adjROI']
        #check all data have the same transDate
        if transDates is None:
            transDates = data.index.values
        if not np.all(transDates == data.index.values):
            raise ValueError('symbol %s do not have the same trans. dates'%(symbol))
        dfs.append(data)
    
    #fixed transDate data
    transDates = transDates[hist_day:]
    
    n_rv, T = len(symbols), dfs[0].index.size - hist_day - 1 
    fullRiskyRetMtx = np.empty((n_rv, hist_day+T+1))
    for idx, df in enumerate(dfs):
        fullRiskyRetMtx[idx, :] = df['adjROI'].values/100.
    
    riskFreeRetVec = np.zeros(T+1)
    buyTransFeeMtx = np.ones((n_rv, T)) * buyTransFee
    sellTransFeeMtx = np.ones((n_rv, T))* sellTransFee
    
    #allocated [0, n_rv-1]為已配置在risky asset的金額，第n_rv為cash
    allocatedVec = np.zeros(n_rv+1)
    allocatedVec[-1] = money
    
    return {
        "n_rv": n_rv,
        "T": T,
        "fullRiskyRetMtx": fullRiskyRetMtx,         #size: n_rv * (hist_day+T+1)
        "riskFreeRetVec": riskFreeRetVec,   #size: n_rv
        "buyTransFeeMtx": buyTransFeeMtx,   #size: n_rv * T
        "sellTransFeeMtx": sellTransFeeMtx, #size: n_rv * T
        "allocatedVec": allocatedVec,       #size: (n_rv + 1)
        "transDates": transDates            #size: (hist_day+T+1)
        }


def constructScenarioStructureFile(n_scenario, probs):
    '''
    產生ScenarioStructure.dat檔案 (nodebased) for pysp
    @param n_scenario, positive integer, scenario個數
    @param probs, numpy.array, size: n_scenario, 每個scenario發生的機率
    '''
    assert len(probs) == n_scenario
    assert np.all(probs >= 0)
    
    data = StringIO()
    #declare node base
    data.write('param ScenarioBasedData := False ;\n')
    
    #stage
    data.write('set Stages := FirstStage SecondStage ;\n')
    
    #set nodes
    data.write('set Nodes : = \n')
    data.write(' ' *4 + 'RootNode\n')
    for scen in xrange(n_scenario):
        data.write(' ' *4 + 'Node%s\n'%(scen))
    data.write(';\n\n')
    
    #tree level
    data.write('param NodeStage := \n')
    data.write(" " * 4 + 'RootNode FirstStage \n')
    for scen in xrange(n_scenario):
        data.write(" " * 4 + "Node%s SecondStage\n"%(scen))
    data.write(';\n\n')
    
    #tree arc
    data.write('set Children[RootNode] := \n')
    for scen in  xrange(n_scenario):
        data.write(" " * 4 + 'Node%s\n'%(scen))
    data.write(';\n\n')

    #probability
    data.write('param ConditionalProbability := \n')
    data.write(' ' *4 + 'RootNode 1.0\n')
    for scen in  xrange(n_scenario):
        data.write(" " * 4 + 'Node%s %s\n'%(scen, probs[scen]))
    data.write(';\n\n')

    #scenario
    data.write('set Scenarios := \n')
    for scen in xrange(n_scenario):
        data.write(" " * 4 + "Scenario%s\n"%(scen))
    data.write(';\n\n')
    
    #mapping scenario to leaf
    data.write('param ScenarioLeafNode := \n')
    for scen in  xrange(n_scenario):
        data.write(" " * 4 + 'Scenario%s Node%s\n'%(scen, scen))
    data.write(';\n\n')
    
    #stage variable
    data.write('set StageVariables[FirstStage] :=  buys[*] sells[*];\n')
    data.write('set StageVariables[SecondStage] := riskyWealth[*] riskFreeWealth;\n')
   
    
    #stage wealth
    data.write('param StageCostVariable := FirstStage  FirstStageWealth\n')
    data.write(' '* 21 + 'SecondStage SecondStageWealth ;')
    
    fileName = os.path.join(FileDir, 'models', 'ScenarioStructure.dat')
    with open(fileName, 'w') as fout:
        fout.write(data.getvalue())
        
    data.close()
    

def generatingScenarios(moments, corrMtx, n_scenario, debug=False):
    '''
    --使用scengen_HKW產生scenario, 使用前tg_moms.txt與tg_corrs.txt必須存在
    '''
    if platform.uname()[0] == 'Linux':
        exe = 'scengen_HKW'
    elif platform.uname()[0] == 'Windows':
        exe = 'scengen_HKW.exe'
    
    _constructTargetMomentFile(moments)    
    _constructTargetcorrMtxFile(corrMtx)
    
    moments = os.path.join(FileDir, 'tg_moms.txt')
    corrMtx = os.path.join(FileDir, 'tg_corrs.txt')
    if not os.path.exists(moments):
        raise ValueError('file %s does not exists'%(moments))
    
    if not os.path.exists(corrMtx):
        raise ValueError('file %s does not exists'%(corrMtx))
    
    rc = subprocess.call('%s %s -f 1'%(exe, n_scenario), shell=True)
    
    probVec, scenarioMtx = parseSamplingMtx(fileName='out_scen.txt')
    if debug:
        os.remove('tg_moms.txt')
        os.remove('tg_corrs.txt')
        os.remove('out_scen.txt')
    
    return probVec, scenarioMtx
    

def constructRootNodeFile(symbols, allocatedWealth, depositWealth,
                          riskFreeRet, buyTransFee, sellTransFee):
    '''
    產生RootNode.dat for pysp
    @param symbols, list, list of symbols
    @param allocatedWealth, numpy.array, size: n_rv, 已分配到各symbol的資產
    @param depositWealth, float, 存款金額
    @param riskFreeRet, float, 存款利率
    @param buyTransFee, numpy.array, size: n_rv, 買進手續費
    @param sellTransFee, numpy.array, size: n_rv, 賣出手續費 
    '''
    #RootNode.dat, deterministic parameters
    rootData = StringIO()
    rootData.write('set symbols := %s ;\n'%(" ".join(symbols)))
    rootData.write('param allocatedWealth : = %s ;\n'%( " ".join(str(v) for v in allocatedWealth)) )
    rootData.write('param depositWealth : = %s ;\n'%(depositWealth))
    rootData.write('param riskFreeRet : = %s ;\n'%(riskFreeRet))
    rootData.write('param buyTransFee : = %s ;\n'%( " ".join(str(v) for v in buyTransFee)) )
    rootData.write('param sellTransFee : = %s ;\n'%(" ".join(str(v) for v in sellTransFee)) )
 
    rootFileName = os.path.join('models', 'RootNode.dat')
    with open (rootFileName, 'w') as fout:
        fout.write(rootData.getvalue())
    rootData.close()
    
    
def constructScenarioFiles( n_scenario, symbols, scenarioMtx, debug=True):
    '''
    與Node[num].dat檔案(node based) for pysp
    @param n_scenario, positive integer, scenario個數
    @param symbols, list
    @param samplingRetMtx, numpy.array, size: n_rv * n_scenario
    '''
    assert scenarioMtx.shape[0] == len(symbols)
    assert scenarioMtx.shape[1] == n_scenario
    
    for sdx in xrange(n_scenario):
        scenData = StringIO()
        scen = scenarioMtx[:, sdx]
        scenData.write('param riskyRet : = %s ;'%(" ".join(str(v) for v in scen)))
        #檔名必須與ScenarioStrucutre.dat中一致
        scenFileName = os.path.join(FileDir, 'models', 'Node%s.dat'%(sdx))
        with open (scenFileName, 'w') as fout:
            fout.write(scenData.getvalue())
        scenData.close()
    
    if debug:
        for sdx in xrange(n_scenario):
            scenFileName = os.path.join(FileDir, 'models', 'Node%s.dat'%(sdx))
            os.remove(scenFileName)    
     
        
def _constructTargetMomentFile(moments):
    '''
    @param moments, numpy.array, size: n_rv * 4
    file format:
    first row: 4, n_rv
    then the matrix size: 4 * n_rv
    -可在matrix之後加入任何註解
    '''
    assert moments.shape[1] == 4
    
    n_rv = moments.shape[0]
    data = StringIO()
    data.write('4\n%s\n'%(n_rv))
    
    mom = moments.T
    #write moment
    for rdx in xrange(4):
        data.write(" ".join(str(v) for v in mom[rdx]))
        data.write('\n')
    
        
    fileName = os.path.join(FileDir, 'tg_moms.txt')
    with open (fileName, 'w') as fout:
        fout.write(data.getvalue())
    data.close()

    
def _constructTargetcorrMtxFile(corrMtx):
    '''file format:
    first row: n_rv, n_rv
    then the matrix size: n_rv * n_rv
    -可在matrix之後加入任何註解
    '''
    n_rv, n_rv2 = corrMtx.shape
    assert n_rv == n_rv2
    print "start tg_corr.txt"
    data = StringIO()
    data.write('%s\n%s\n'%(n_rv, n_rv))
    
    for rdx in xrange(n_rv):
        data.write(" ".join(str(v) for v in corrMtx[rdx, :]))
        data.write('\n')
        
    fileName = os.path.join(FileDir, 'tg_corrs.txt')
    with open (fileName, 'w') as fout:
        fout.write(data.getvalue())
    data.close()
    

def parseSamplingMtx(fileName='out_scen.txt'):
    '''讀取moment matching所取樣出的變數
    #開頭的為註解行
    each row is a scenario, and 
    the first element is the probability,
    the second element is the first variable of the scenario, 
    the third element is the second varible of the scenario,
    ...
    therefore each row (scenario) contains (n_rv+1) elements
    
    -可用numpy.genfromtxt方法讀取
    
    return sample matrix, numpy.array, size: n_rv * n_scenario
    '''
    with open(fileName) as fin:
        mtx = np.genfromtxt(fin)
        
    probVec = mtx[:, 0]
    scenarioMtx = mtx[:, (1,2)].T
    return probVec, scenarioMtx
 
    
        
        
        
def fixedSymbolSPPortfolio(symbols, startDate, endDate,  money=1e6,
                           hist_day=20, n_scenario=1000):
    '''
    -固定投資標的物(symbols)，只考慮buy, sell的交易策略
    -假設symbols有n_rv個，投資期數共T期(最後一期不買賣，只結算)
    
    @param symbols, list, target assets
    @param startDate, endDate, datetime.date, 交易的起始，結束日期
    @param money, positive float, 初使資金
    @param hist_day, positive integer, 用於計算moment與corr mtx的歷史資料長度
    @param n_scenario, positive integer, 每一期產生的scenario個數
    
    @return translog 
        { "n_rv": n_rv,
        "T": T,
        "riskyRetMtx": riskyRetMtx,         #size: n_rv * (hist_day+T+1)
        "riskFreeRetVec": riskFreeRetVec,   #size: n_rv
        "buyTransFeeMtx": buyTransFeeMtx,   #size: n_rv * T
        "sellTransFeeMtx": sellTransFeeMtx, #size: n_rv * T
        "allocatedVec": allocatedVec,       #size: (n_rv + 1)
        "transDates": transDates   
        }
    '''
    param = constructModelMtx(symbols, startDate, endDate, money)
    n_rv, T =param['n_rv'], param['T']
    fullRiskyRetMtx = param['fullRiskyRetMtx']
    riskFreeRetVec = param['riskFreeRetVec']
    buyTransFeeMtx = param['buyTransFeeMtx']
    sellTransFeeMtx = param['sellTransFeeMtx']
    transDates = param['transDates']
    
    #setup result directory
    resultDir = os.path.join(ExpResultsDir, "%s_%s"%(
                        fixedSymbolSPPortfolio.__name__, 
                        time.strftime("%y%m%d_%H%M%S")))
    
    if not os.path.exists(resultDir):
        os.mkdir(resultDir)
    
    #每一期的ScenarioStructure都一樣，建一次即可
    probs = np.ones(n_scenario, dtype=np.float)/n_scenario
    constructScenarioStructureFile(n_scenario, probs)
    
    for tdx in xrange(T):
        transDate = transDates[tdx]
        transDateDir = os.path.join(resultDir, transDate)
        if not os.path.exists(transDateDir):
            os.mkdir(transDateDir)
        
        #投資時已知當日的ret(即已經知道當日收盤價)
        #算出4 moments與correlation matrix
        subRiskyRetMtx = fullRiskyRetMtx[:,tdx:hist_day]
        moments = np.empty((n_rv, 4))
        moments[:, 0] = subRiskyRetMtx.mean(axis=1)
        moments[:, 1] = subRiskyRetMtx.std(axis=1)
        moments[:, 2] = spstats.skew(subRiskyRetMtx, axis=1)
        moments[:, 3] = spstats.kurtosis(subRiskyRetMtx, axis=1)
        corrMtx = np.corrcoef(subRiskyRetMtx)
       
        #call scngen_HKW抽出下一期的樣本中
        probVec, scenarioMtx = generatingScenarios(moments, corrMtx, n_scenario)
        
        #使用抽樣樣本建立ScenarioStructure.dat, RootNode.dat與不同scenario的檔案
        constructRootNodeFile(symbols, allocatedWealth, depositWealth,
                          riskFreeRet, buyTransFee, sellTransFee)
        
        constructScenarioFiles(n_scenario, symbols, scenarioMtx)
        
        #使用抽出的樣本解SP(runef)，得到最佳的買進，賣出金額
        modelDir = os.path.join(FileDir, "models")
        cmd = 'runef -i %s -m %s  --solution-writer=coopr.pysp.csvsolutionwriter --solver=cplex --solve'%(
                modelDir, modelDir)
        rc = subprocess.call(cmd, shell=True)
    
        #parse results, 並且執行買賣
    
        #更新wealthProcess與singalProcess
        pass
    
    #最後一期只結算不買賣
    
    
    

if __name__ == '__main__':
    startDate = date(2004,1, 1)
    endDate = date(2004, 1, 10)
    symbols = ['1101', '1102']
    money = 1e5
    hist_day = 5
#     constructModelMtx(symbols, startDate, endDate, money, hist_day)
    
    n_rv = len(symbols)
    allocatedWealth = np.ones(n_rv) * 100.0
    depositWealth = 1e5
    riskFreeRet = 0.
    buyTransFee = np.ones(n_rv) * 0.003
    sellTransFee = np.ones(n_rv) * 0.004425
#     constructRootNodeFile(symbols, allocatedWealth, depositWealth,
#                           riskFreeRet, buyTransFee, sellTransFee)
    n_scenario = 10
    data = np.random.randn(n_rv, n_scenario)
    moments = np.empty((n_rv, 4))
    moments[:, 0] = data.mean(axis=1)
    moments[:, 1] = data.std(axis=1)
    moments[:, 2] = spstats.skew(data, axis=1)
    moments[:, 3] = spstats.kurtosis(data, axis=1)
    corrMtx = np.corrcoef(data)
    
    debug=False
    prob, scenMtx = generatingScenarios(moments, corrMtx, n_scenario, debug)
    constructScenarioFiles( n_scenario, symbols, scenMtx, debug)