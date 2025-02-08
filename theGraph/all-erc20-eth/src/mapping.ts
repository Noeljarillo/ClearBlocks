// from https://github.com/georgeroman/erc20-subgraph
import { BigDecimal, ethereum, BigInt, Bytes } from "@graphprotocol/graph-ts";

import { Approval, ERC20, Transfer } from "../generated/ERC20/ERC20";
import {
  Account,
  Token,
  TokenApproval,
  TokenBalance,
  Transfer as TransferEntity,
} from "../generated/schema";

const zeroAddress = '0x0000000000000000000000000000000000000000';

function loadOrCreateAccount(address: string): Account | null {
  let account = Account.load(address);
  if (!account) {
    account = new Account(address);
    account.save();
  }
  return account;
}

function loadOrCreateToken(event: ethereum.Event): Token | null {
  let token = Token.load(event.address.toHex());
  if (!token) {
    let erc20 = ERC20.bind(event.address);
    token = new Token(event.address.toHex());

    let nameResult = erc20.try_name();
    if (!nameResult.reverted) {
      token.name = nameResult.value;
    }

    let symbolResult = erc20.try_symbol();
    if (!symbolResult.reverted) {
      token.symbol = symbolResult.value;
    }

    let decimalsResult = erc20.try_decimals();
    if (!decimalsResult.reverted) {
      // Still check for valid decimals range
      if (decimalsResult.value.toBigDecimal().gt(BigDecimal.fromString("255"))) {
        return null;
      }
      token.decimals = decimalsResult.value.toI32();
    } else {
      // Default to 18 decimals if we can't read it
      token.decimals = 18;
    }

    token.save();
  }
  return token;
}

export function handleApproval(event: Approval): void {
  let token = loadOrCreateToken(event);
  if (!token) {
    return;
  }

  let owner = event.params.owner.toHex();
  let spender = event.params.spender.toHex();
  let value = event.params.value.toBigDecimal();

  let ownerAccount = loadOrCreateAccount(owner);
  let spenderAccount = loadOrCreateAccount(spender);

  if (!ownerAccount || !spenderAccount) {
    return;
  }

  let tokenApproval = TokenApproval.load(
    token.id + "-" + ownerAccount.id + "-" + spenderAccount.id
  );
  if (!tokenApproval) {
    tokenApproval = new TokenApproval(
      token.id + "-" + ownerAccount.id + "-" + spenderAccount.id
    );
    tokenApproval.token = token.id;
    tokenApproval.ownerAccount = ownerAccount.id;
    tokenApproval.spenderAccount = spenderAccount.id;
  }
  tokenApproval.value = value;
  tokenApproval.save();
}

export function handleTransfer(event: Transfer): void {
  let token = loadOrCreateToken(event);
  if (!token) {
    return;
  }

  let from = event.params.from.toHex();
  let to = event.params.to.toHex();
  let value = event.params.value.toBigDecimal();

  let fromAccount = loadOrCreateAccount(from);
  let toAccount = loadOrCreateAccount(to);

  if (!fromAccount || !toAccount) {
    return;
  }

  // Handle token balances
  if (fromAccount.id != zeroAddress) {
    let fromTokenBalance = TokenBalance.load(token.id + "-" + fromAccount.id);
    if (!fromTokenBalance) {
      fromTokenBalance = new TokenBalance(token.id + "-" + fromAccount.id);
      fromTokenBalance.token = token.id;
      fromTokenBalance.account = fromAccount.id;
      fromTokenBalance.value = BigDecimal.fromString("0");
    }
    fromTokenBalance.value = fromTokenBalance.value.minus(value);
    fromTokenBalance.save();
  }

  let toTokenBalance = TokenBalance.load(token.id + "-" + toAccount.id);
  if (!toTokenBalance) {
    toTokenBalance = new TokenBalance(token.id + "-" + toAccount.id);
    toTokenBalance.token = token.id;
    toTokenBalance.account = toAccount.id;
    toTokenBalance.value = BigDecimal.fromString("0");
  }
  toTokenBalance.value = toTokenBalance.value.plus(value);
  toTokenBalance.save();

  // Create Transfer entity
  let transfer = new TransferEntity(
    event.transaction.hash.toHexString() + "-" + event.logIndex.toString()
  );
  transfer.from = event.params.from;
  transfer.to = event.params.to;
  transfer.value = event.params.value;
  transfer.blockTimestamp = event.block.timestamp;
  
  // Calculate day - convert timestamp to days since epoch
  let dayTimestamp = event.block.timestamp.div(BigInt.fromI32(86400));
  transfer.day = dayTimestamp.toString();
  
  transfer.save();
}