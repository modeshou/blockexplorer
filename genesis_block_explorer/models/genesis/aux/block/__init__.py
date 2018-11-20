import sqlalchemy
from sqlalchemy.ext.hybrid import hybrid_method

from flask import current_app as app

from .....db import db
from .....logging import get_logger
from ..utils import update_dict_with_key_id, update_dict_with_time
from ..generic.prev_next_item import PrevNextItemMixin

def get_req_models(bind_key=None):
    from .header import HeaderModel
    from ..tx import TxModel
    from ..tx.param import ParamModel
    if bind_key:
        HeaderModel.__bind_key__ = bind_key
        TxModel.__bind_key__ = bind_key
        ParamModel.__bind_key__ = bind_key
    return HeaderModel, TxModel, ParamModel

logger = get_logger(app) 
get_req_models()

class BlockPrevNextItemMixin(PrevNextItemMixin):
    @hybrid_method
    def get_prev_next_info(self, **kwargs):
        session = kwargs.get('session', db.session)
        has_prev = self.has_prev(session=session)
        if has_prev:
            prev_block_id = self.prev(session=session).id
        else:
            prev_block_id = 0
        has_next = self.has_next(session=session)
        if has_next:
            next_block_id = self.next(session=session).id
        else:
            next_block_id = 0
        info = {
            'has_prev': has_prev,
            'prev_block_id': prev_block_id, 
            'has_next': has_next,
            'next_block_id': next_block_id, 
        }
        return info

class BlockModel(db.Model, BlockPrevNextItemMixin):

    __tablename__ = 'blocks'

    id = db.Column(db.Integer, primary_key=True, comment="Block ID")
    time_dt = db.Column(db.String, comment="Time")
    hash = db.Column(db.String, comment="Hash")
    ukey_id = db.Column(db.String, comment="Key ID")
    ecosystem_id = db.Column(db.Integer, comment="EcoSystem ID")
    node_position = db.Column(db.Integer, comment="Node Position")
    tx_count = db.Column(db.Integer, comment="Number of Transactions")

    #header
    header_id = db.Column(db.Integer, db.ForeignKey('blocks_headers.id'),
                          comment="Header Record ID")
    header = db.relationship('HeaderModel',
                             backref=db.backref('block', uselist=False))

    # main
    key_id = db.Column(db.BigInteger, comment="Raw Key ID")
    time_ts = db.Column(db.Integer, comment="Time (Stamp)")
    time_dtu = db.Column(db.String, comment="Time (UTC)")
    rollbacks_hash = db.Column(db.String, comment="Rollbacks Hash")
    mrkl_root = db.Column(db.String, comment="Merkle Root")
    bin_data = db.Column(db.String, comment="Bin Data")
    gen_block = db.Column(db.Boolean, comment="Gen BLock")
    sys_update = db.Column(db.Boolean, comment="Sys Update")
    stop_count = db.Column(db.Integer, comment="Stop Count")
    transactions = db.relationship('TxModel', uselist=True,
                                   backref=db.backref('blocks'))


    @classmethod
    def prepare_from_dict(cls, data, **kwargs):
        block_id = int(data.pop('block_id'))
        data.update({'id': block_id})
        header = data.pop('header')
        txs_data = data.pop('transactions')
        data = update_dict_with_key_id(data)
        time = data.get('time')
        data = update_dict_with_time(data)
        return time, data, header, txs_data

    @classmethod
    def update_from_dict(cls, data, **kwargs):
        session = kwargs.get('session', db.session)
        HeaderModel, TxModel, ParamModel = get_req_models()
        time, data, header, txs_data = cls.prepare_from_dict(data)
        block = cls(**data)
        session.add(block)
        block.header = HeaderModel.update_from_dict(header, session=session)
        non_contract_tx = False
        txs = []
        for tx_data in txs_data:
            # TODO: fix it in backend api
            if 'time' not in tx_data or not tx_data['time'] and time:
                tx_data['time'] = time
            if 'key_id' not in tx_data or not tx_data['key_id']:
                tx_data['key_id'] = data['key_id']

            tx = TxModel.update_from_dict(tx_data, session=session,
                                          db_session_commit_enabled=False)
            block.transactions.append(tx)
            txs.append(tx)
        if kwargs.get('db_session_commit_enabled', True):
            session.commit()
        return data, txs

    @classmethod
    def update_from_block(cls, block, **kwargs):
        session = kwargs.get('session', db.session)
        data = block.to_dict(style='snake', struct_style='sqlalchemy')
        if kwargs.get('db_session_commit_enabled', True):
            session.commit()
        return cls.update_from_dict(data, session=session,
        db_session_commit_enabled=kwargs.get('db_session_commit_enabled', True))

    @classmethod
    def update_from_block_set(cls, block_set, **kwargs):
        session = kwargs.get('session', db.session)
        l = []
        for block in block_set.blocks:
            l.append(cls.update_from_block(block, session=session,
                                           db_session_commit_enabled=False))
        #blocks_data = block_set.to_detailed_list(style='snake')
        #l = []
        #for data in blocks_data:
        #    l.append(cls.update_from_dict(data, session=session,
        #                                  db_session_commit_enabled=False))
        if kwargs.get('db_session_commit_enabled', True):
            session.commit()
        return l


