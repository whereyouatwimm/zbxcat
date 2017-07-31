#!/usr/bin/env python3

# Based on spend-p2sh-txout.py from python-bitcoinlib.
# Copyright (C) 2017 The Zcash developers

import sys
if sys.version_info.major < 3:
    sys.stderr.write('Sorry, Python 3.x required by this example.\n')
    sys.exit(1)

import zcash
import zcash.rpc
from zcash import SelectParams
from zcash.core import b2x, lx, x, b2lx, COIN, COutPoint, CMutableTxOut, CMutableTxIn, CMutableTransaction, Hash160
from zcash.core.script import CScript, OP_DUP, OP_IF, OP_ELSE, OP_ENDIF, OP_HASH160, OP_EQUALVERIFY, OP_CHECKSIG, SignatureHash, SIGHASH_ALL, OP_FALSE, OP_DROP, OP_CHECKLOCKTIMEVERIFY, OP_SHA256, OP_TRUE
from zcash.core.scripteval import VerifyScript, SCRIPT_VERIFY_P2SH
from zcash.wallet import CBitcoinAddress, CBitcoinSecret, P2SHBitcoinAddress, P2PKHBitcoinAddress

from xcat.utils import *

# SelectParams('testnet')
SelectParams('regtest')
# TODO: accurately read user and pw info
zcashd = zcash.rpc.Proxy(service_url="http://user:password@127.0.0.1:18232")
FEE = 0.001*COIN

def validateaddress(addr):
    return zcashd.validateaddress(addr)

def get_keys(funder_address, redeemer_address):
    fundpubkey = CBitcoinAddress(funder_address)
    redeempubkey = CBitcoinAddress(redeemer_address)
    # fundpubkey = zcashd.getnewaddress()
    # redeempubkey = zcashd.getnewaddress()
    return fundpubkey, redeempubkey

def privkey(address):
    zcashd.dumpprivkey(address)

def hashtimelockcontract(funder, redeemer, commitment, locktime):
    funderAddr = CBitcoinAddress(funder)
    redeemerAddr = CBitcoinAddress(redeemer)
    if type(commitment) == str:
        commitment = x(commitment)
    # h = sha256(secret)
    blocknum = zcashd.getblockcount()
    print("Current blocknum", blocknum)
    redeemblocknum = blocknum + locktime
    print("REDEEMBLOCKNUM ZCASH", redeemblocknum)
    print("COMMITMENT on zxcat", commitment)
    # can rm op_dup and op_hash160 if you replace addrs with pubkeys (as raw hex/bin data?), and can rm last op_equalverify (for direct pubkey comparison)
    zec_redeemScript = CScript([OP_IF, OP_SHA256, commitment, OP_EQUALVERIFY,OP_DUP, OP_HASH160,
                                 redeemerAddr, OP_ELSE, redeemblocknum, OP_CHECKLOCKTIMEVERIFY, OP_DROP, OP_DUP, OP_HASH160,
                                 funderAddr, OP_ENDIF,OP_EQUALVERIFY, OP_CHECKSIG])
    print("Redeem script for p2sh contract on Zcash blockchain:", b2x(zec_redeemScript))
    txin_scriptPubKey = zec_redeemScript.to_p2sh_scriptPubKey()
    # Convert the P2SH scriptPubKey to a base58 Bitcoin address
    txin_p2sh_address = CBitcoinAddress.from_scriptPubKey(txin_scriptPubKey)
    p2sh = str(txin_p2sh_address)
    print("p2sh computed", p2sh)
    # Returning all this to be saved locally in p2sh.json
    return {'p2sh': p2sh, 'redeemblocknum': redeemblocknum, 'redeemScript': b2x(zec_redeemScript), 'redeemer': redeemer, 'funder': funder, 'locktime': locktime}

def fund_htlc(p2sh, amount):
    send_amount = float(amount)*COIN
    fund_txid = zcashd.sendtoaddress(p2sh, send_amount)
    txid = b2x(lx(b2x(fund_txid)))
    return txid

def check_funds(p2sh):
    zcashd.importaddress(p2sh, "", False)
    print("Imported address", p2sh)
    # Get amount in address
    amount = zcashd.getreceivedbyaddress(p2sh, 0)
    print("Amount in address", amount)
    amount = amount/COIN
    return amount

def get_tx_details(txid):
    fund_txinfo = zcashd.gettransaction(txid)
    return fund_txinfo['details'][0]

def find_transaction_to_address(p2sh):
    zcashd.importaddress(p2sh, "", False)
    txs = zcashd.listunspent(0, 100)
    for tx in txs:
        # print("tx addr:", tx['address'])
        # print(type(tx['address']))
        # print(type(p2sh))
        if tx['address'] == CBitcoinAddress(p2sh):
            print("Found tx to p2sh", p2sh)
            print(tx)
            return tx

# def get_tx_details(txid):
#     # This method is problematic I haven't gotten the type conversions right
#     print(bytearray.fromhex(txid))
#     print(b2x(bytearray.fromhex(txid)))
#     fund_txinfo = zcashd.gettransaction(bytearray.fromhex(txid))
#     print(fund_txinfo)
#
#     return fund_txinfo['details'][0]

def find_secret(p2sh):
    return parse_secret('4c25b5db9f3df48e48306891d8437c69308afa122f92416df1a3ba0d3604882f')
    zcashd.importaddress(p2sh, "", False)
    # is this working?
    txs = zcashd.listtransactions()
    for tx in txs:
        # print("tx addr:", tx['address'])
        # print(type(tx['address']))
        # print(type(p2sh))
        if (tx['address'] == p2sh ) and (tx['category'] == "send"):
            print(type(tx['txid']))
            print(str.encode(tx['txid']))
            raw = zcashd.getrawtransaction(lx(tx['txid']),True)['hex']
            decoded = zcashd.decoderawtransaction(raw)
            print("deo:", decoded['vin'][0]['scriptSig']['asm'])

def parse_secret(txid):
    raw = zcashd.gettransaction(lx(txid), True)['hex']
    # print("Raw", raw)
    decoded = zcashd.decoderawtransaction(raw)
    scriptSig = decoded['vin'][0]['scriptSig']
    print("Decoded", scriptSig)
    asm = scriptSig['asm'].split(" ")
    pubkey = asm[1]
    secret = x2s(asm[2])
    redeemPubkey = P2PKHBitcoinAddress.from_pubkey(x(pubkey))
    print('redeemPubkey', redeemPubkey)
    print(secret)
    return secret

# redeems automatically after buyer has funded tx, by scanning for transaction to the p2sh
# i.e., doesn't require buyer telling us fund txid
def auto_redeem(contract, secret):
    # How to find redeemScript and redeemblocknum from blockchain?
    print("Contract in auto redeem", contract.__dict__)
    p2sh = contract.p2sh
    #checking there are funds in the address
    amount = check_funds(p2sh)
    if(amount == 0):
        print("address ", p2sh, " not funded")
        quit()
    fundtx = find_transaction_to_address(p2sh)
    amount = fundtx['amount'] / COIN
    print("Found fundtx:", fundtx)
    p2sh = P2SHBitcoinAddress(p2sh)
    if fundtx['address'] == p2sh:
        print("Found {0} in p2sh {1}, redeeming...".format(amount, p2sh))

        # Where can you find redeemblocknum in the transaction?
        redeemblocknum = find_redeemblocknum(contract)
        blockcount = zcashd.getblockcount()
        print("\nCurrent blocknum at time of redeem on Zcash:", blockcount)
        if blockcount < redeemblocknum:
            redeemPubKey = find_redeemAddr(contract)
            print('redeemPubKey', redeemPubKey)
            zec_redeemScript = CScript(x(contract.redeemScript))
            txin = CMutableTxIn(fundtx['outpoint'])
            txout = CMutableTxOut(fundtx['amount'] - FEE, redeemPubKey.to_scriptPubKey())
            # Create the unsigned raw transaction.
            tx = CMutableTransaction([txin], [txout])
            sighash = SignatureHash(zec_redeemScript, tx, 0, SIGHASH_ALL)
            # TODO: figure out how to better protect privkey
            privkey = zcashd.dumpprivkey(redeemPubKey)
            sig = privkey.sign(sighash) + bytes([SIGHASH_ALL])
            print("SECRET", secret)
            preimage = secret.encode('utf-8')
            txin.scriptSig = CScript([sig, privkey.pub, preimage, OP_TRUE, zec_redeemScript])

            print("txin.scriptSig", b2x(txin.scriptSig))
            txin_scriptPubKey = zec_redeemScript.to_p2sh_scriptPubKey()
            print('Redeem txhex', b2x(tx.serialize()))
            VerifyScript(txin.scriptSig, txin_scriptPubKey, tx, 0, (SCRIPT_VERIFY_P2SH,))
            print("script verified, sending raw tx")
            txid = zcashd.sendrawtransaction(tx)
            print("Txid of submitted redeem tx: ", b2x(lx(b2x(txid))))
            print("TXID SUCCESSFULLY REDEEMED")
            return 'redeem_tx', b2x(lx(b2x(txid)))
        else:
            # if blockcount >= redeemblocknum:
            #     tx.nLockTime = redeemblocknum
            print("nLocktime exceeded, refunding")
            refundPubKey = find_refundAddr(contract)
            print('refundPubKey', refundPubKey)
            txid = zcashd.sendtoaddress(refundPubKey, fundtx['amount'] - FEE)
            print("Txid of refund tx:",  b2x(lx(b2x(txid))))
            print("TXID SUCCESSFULLY REFUNDED")
            return 'refund_tx', b2x(lx(b2x(txid)))
    else:
        print("No contract for this p2sh found in database", p2sh)

def redeem_contract(contract, secret):
    # How to find redeemScript and redeemblocknum from blockchain?
    print("Contract in redeem contract", contract.__dict__)
    p2sh = contract.p2sh
    #checking there are funds in the address
    amount = check_funds(p2sh)
    if(amount == 0):
        print("address ", p2sh, " not funded")
        quit()
    fundtx = find_transaction_to_address(p2sh)
    amount = fundtx['amount'] / COIN
    print("Found fundtx:", fundtx)
    p2sh = P2SHBitcoinAddress(p2sh)
    if fundtx['address'] == p2sh:
        print("Found {0} in p2sh {1}, redeeming...".format(amount, p2sh))

        # Where can you find redeemblocknum in the transaction?
        # redeemblocknum = find_redeemblocknum(contract)
        blockcount = zcashd.getblockcount()
        print("\nCurrent blocknum at time of redeem on Zcash:", blockcount)
        if blockcount < contract.redeemblocknum:
            # TODO: parse the script once, up front.
            redeemPubKey = find_redeemAddr(contract)


            print('redeemPubKey', redeemPubKey)
            zec_redeemScript = CScript(x(contract.redeemScript))
            txin = CMutableTxIn(fundtx['outpoint'])
            txout = CMutableTxOut(fundtx['amount'] - FEE, redeemPubKey.to_scriptPubKey())
            # Create the unsigned raw transaction.
            tx = CMutableTransaction([txin], [txout])
            sighash = SignatureHash(zec_redeemScript, tx, 0, SIGHASH_ALL)
            # TODO: figure out how to better protect privkey
            privkey = zcashd.dumpprivkey(redeemPubKey)
            sig = privkey.sign(sighash) + bytes([SIGHASH_ALL])
            print("SECRET", secret)
            preimage = secret.encode('utf-8')
            txin.scriptSig = CScript([sig, privkey.pub, preimage, OP_TRUE, zec_redeemScript])

            print("txin.scriptSig", b2x(txin.scriptSig))
            txin_scriptPubKey = zec_redeemScript.to_p2sh_scriptPubKey()
            print('Redeem txhex', b2x(tx.serialize()))
            VerifyScript(txin.scriptSig, txin_scriptPubKey, tx, 0, (SCRIPT_VERIFY_P2SH,))
            print("script verified, sending raw tx")
            txid = zcashd.sendrawtransaction(tx)
            print("Txid of submitted redeem tx: ", b2x(lx(b2x(txid))))
            print("TXID SUCCESSFULLY REDEEMED")
            return 'redeem_tx', b2x(lx(b2x(txid)))
        else:
            print("nLocktime exceeded, refunding")
            refundPubKey = find_refundAddr(contract)
            print('refundPubKey', refundPubKey)
            txid = zcashd.sendtoaddress(refundPubKey, fundtx['amount'] - FEE)
            print("Txid of refund tx:",  b2x(lx(b2x(txid))))
            print("TXID SUCCESSFULLY REFUNDED")
            return 'refund_tx', b2x(lx(b2x(txid)))
    else:
        print("No contract for this p2sh found in database", p2sh)

def parse_script(script_hex):
    redeemScript = zcashd.decodescript(script_hex)
    scriptarray = redeemScript['asm'].split(' ')
    return scriptarray

def find_redeemblocknum(contract):
    print("In find_redeemblocknum")
    scriptarray = parse_script(contract.redeemScript)
    print("Returning scriptarray", scriptarray)
    redeemblocknum = scriptarray[8]
    return int(redeemblocknum)

def find_redeemAddr(contract):
    scriptarray = parse_script(contract.redeemScript)
    redeemer = scriptarray[6]
    redeemAddr = P2PKHBitcoinAddress.from_bytes(x(redeemer))
    return redeemAddr

def find_refundAddr(contract):
    scriptarray = parse_script(contract.redeemScript)
    funder = scriptarray[13]
    refundAddr = P2PKHBitcoinAddress.from_bytes(x(funder))
    return refundAddr

def find_recipient(contract):
    # make this dependent on actual fund tx to p2sh, not contract
    txid = contract.fund_tx
    raw = zcashd.gettransaction(lx(txid), True)['hex']
    # print("Raw", raw)
    decoded = zcashd.decoderawtransaction(raw)
    scriptSig = decoded['vin'][0]['scriptSig']
    print("Decoded", scriptSig)
    asm = scriptSig['asm'].split(" ")
    pubkey = asm[1]
    initiator = CBitcoinAddress(contract.initiator)
    fulfiller = CBitcoinAddress(contract.fulfiller)
    print("Initiator", b2x(initiator))
    print("Fulfiler", b2x(fulfiller))
    print('pubkey', pubkey)
    redeemPubkey = P2PKHBitcoinAddress.from_pubkey(x(pubkey))
    print('redeemPubkey', redeemPubkey)

# addr = CBitcoinAddress('tmFRXyju7ANM7A9mg75ZjyhFW1UJEhUPwfQ')
# print(addr)
# # print(b2x('tmFRXyju7ANM7A9mg75ZjyhFW1UJEhUPwfQ'))
# print(b2x(addr))

def new_zcash_addr():
    addr = zcashd.getnewaddress()
    print('new ZEC addr', addr.to_p2sh_scriptPubKey)
    return addr.to_scriptPubKey()

def generate(num):
    blocks = zcashd.generate(num)
    return blocks