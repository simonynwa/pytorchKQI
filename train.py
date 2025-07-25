import torch
import torch.nn as nn
import torch.nn.functional as F
import torchKQI
import torchvision.models as models
import math
import numpy as np
from tqdm import tqdm
import datetime
import os
import time
import warnings
import classification.presets as presets
import torch
import torch.utils.data
import torchvision
import torchvision.transforms
import classification.utils as utils
from classification.sampler import RASampler
from torch import nn
import pandas as pd
from torch.utils.data.dataloader import default_collate
from torchvision.transforms.functional import InterpolationMode
from classification.transforms import get_mixup_cutmix
from typing import Type, Any, Callable, Union, List, Optional
import torch.nn.init as init
import torch.nn.utils.prune as prune
import random
from torch.utils.data import Subset
from collections import defaultdict


def train_one_epoch(model, criterion, optimizer, data_loader, device, epoch, args, model_ema=None, scaler=None): 
    model.train()
    metric_logger = utils.MetricLogger(delimiter="  ")
    metric_logger.add_meter("lr", utils.SmoothedValue(window_size=1, fmt="{value}"))
    metric_logger.add_meter("img/s", utils.SmoothedValue(window_size=10, fmt="{value}"))

    header = f"Epoch: [{epoch}]"
    for i, (image, target) in enumerate(metric_logger.log_every(data_loader, args.print_freq, header)):
        start_time = time.time()
        image, target = image.to(device), target.to(device)
        with torch.amp.autocast('cuda', enabled=scaler is not None):
            output = model(image)
            loss = criterion(output, target)

        optimizer.zero_grad()
        if scaler is not None:
            scaler.scale(loss).backward()
            if args.clip_grad_norm is not None:
                # we should unscale the gradients of optimizer's assigned params if do gradient clipping
                scaler.unscale_(optimizer)
                nn.utils.clip_grad_norm_(model.parameters(), args.clip_grad_norm)
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            if args.clip_grad_norm is not None:
                nn.utils.clip_grad_norm_(model.parameters(), args.clip_grad_norm)
            optimizer.step()

        if model_ema and i % args.model_ema_steps == 0:
            model_ema.update_parameters(model)
            if epoch < args.lr_warmup_epochs:
                # Reset ema buffer to keep copying weights during warmup period
                model_ema.n_averaged.fill_(0)

        acc1, acc5 = utils.accuracy(output, target, topk=(1, 5))
        batch_size = image.shape[0]
        metric_logger.update(loss=loss.item(), lr=optimizer.param_groups[0]["lr"])
        metric_logger.meters["acc1"].update(acc1.item(), n=batch_size)
        metric_logger.meters["acc5"].update(acc5.item(), n=batch_size)
        metric_logger.meters["img/s"].update(batch_size / (time.time() - start_time))


def evaluate(model, criterion, data_loader, device, print_freq=100, log_suffix=""):
    model.eval()
    metric_logger = utils.MetricLogger(delimiter="  ")
    header = f"Test: {log_suffix}"

    num_processed_samples = 0
    with torch.inference_mode():
        for image, target in metric_logger.log_every(data_loader, print_freq, header):
            image = image.to(device, non_blocking=True)
            target = target.to(device, non_blocking=True)
            output = model(image)
            loss = criterion(output, target)

            acc1, acc5 = utils.accuracy(output, target, topk=(1, 5))
            # FIXME need to take into account that the datasets
            # could have been padded in distributed setup
            batch_size = image.shape[0]
            metric_logger.update(loss=loss.item())
            metric_logger.meters["acc1"].update(acc1.item(), n=batch_size)
            metric_logger.meters["acc5"].update(acc5.item(), n=batch_size)
            num_processed_samples += batch_size
    # gather the stats from all processes

    num_processed_samples = utils.reduce_across_processes(num_processed_samples)
    if (
        hasattr(data_loader.dataset, "__len__")
        and len(data_loader.dataset) != num_processed_samples
        and torch.distributed.get_rank() == 0
    ):
        # See FIXME above
        warnings.warn(
            f"It looks like the dataset has {len(data_loader.dataset)} samples, but {num_processed_samples} "
            "samples were used for the validation, which might bias the results. "
            "Try adjusting the batch size and / or the world size. "
            "Setting the world size to 1 is always a safe bet."
        )

    metric_logger.synchronize_between_processes()

    print(f"{header} Acc@1 {metric_logger.acc1.global_avg:.3f} Acc@5 {metric_logger.acc5.global_avg:.3f}")
    return metric_logger.acc1.global_avg, metric_logger.acc5.global_avg


def _get_cache_path(filepath):
    import hashlib

    h = hashlib.sha1(filepath.encode()).hexdigest()
    cache_path = os.path.join("~", ".torch", "vision", "datasets", "imagefolder", h[:10] + ".pt")
    cache_path = os.path.expanduser(cache_path)
    return cache_path




def load_data(num, traindir, valdir, args):
    # Data loading code
    print("Loading data")
    val_resize_size, val_crop_size, train_crop_size = (
        args.val_resize_size,
        args.val_crop_size,
        args.train_crop_size,
    )
    interpolation = InterpolationMode(args.interpolation)

    print("Loading training data")
    st = time.time()
    cache_path = _get_cache_path(traindir)
    if args.cache_dataset and os.path.exists(cache_path):
        # Attention, as the transforms are also cached!
        print(f"Loading dataset_train from {cache_path}")
        # TODO: this could probably be weights_only=True
        dataset, _ = torch.load(cache_path, weights_only=False)
    else:
        # We need a default value for the variables below because args may come
        # from train_quantization.py which doesn't define them.
        auto_augment_policy = getattr(args, "auto_augment", None)
        random_erase_prob = getattr(args, "random_erase", 0.0)
        ra_magnitude = getattr(args, "ra_magnitude", None)
        augmix_severity = getattr(args, "augmix_severity", None)
        dataset = torchvision.datasets.ImageFolder(
            traindir,
            presets.ClassificationPresetTrain(
                crop_size=train_crop_size,
                interpolation=interpolation,
                auto_augment_policy=auto_augment_policy,
                random_erase_prob=random_erase_prob,
                ra_magnitude=ra_magnitude,
                augmix_severity=augmix_severity,
                backend=args.backend,
                use_v2=args.use_v2,
            ),
        )
        if args.cache_dataset:
            print(f"Saving dataset_train to {cache_path}")
            utils.mkdir(os.path.dirname(cache_path))
            utils.save_on_master((dataset, traindir), cache_path)
    print("Took", time.time() - st)

    class_indices = defaultdict(list)
    for idx, (_, label) in enumerate(dataset.samples):
        class_indices[label].append(idx)

    random.seed(0)
    selected_indices = []
    for indices in class_indices.values():
        selected_indices.extend(random.sample(indices, min(int(num / 1000), len(indices))))

    dataset = Subset(dataset, selected_indices)

    print("Loading validation data")
    cache_path = _get_cache_path(valdir)
    if args.cache_dataset and os.path.exists(cache_path):
        # Attention, as the transforms are also cached!
        print(f"Loading dataset_test from {cache_path}")
        # TODO: this could probably be weights_only=True
        dataset_test, _ = torch.load(cache_path, weights_only=False)
    else:
        if args.weights and args.test_only:
            weights = torchvision.models.get_weight(args.weights)
            preprocessing = weights.transforms(antialias=True)
            if args.backend == "tensor":
                preprocessing = torchvision.transforms.Compose([torchvision.transforms.PILToTensor(), preprocessing])

        else:
            preprocessing = presets.ClassificationPresetEval(
                crop_size=val_crop_size,
                resize_size=val_resize_size,
                interpolation=interpolation,
                backend=args.backend,
                use_v2=args.use_v2,
            )

        dataset_test = torchvision.datasets.ImageFolder(
            valdir,
            preprocessing,
        )
        if args.cache_dataset:
            print(f"Saving dataset_test to {cache_path}")
            utils.mkdir(os.path.dirname(cache_path))
            utils.save_on_master((dataset_test, valdir), cache_path)

    print("Creating data loaders")
    if args.distributed:
        if hasattr(args, "ra_sampler") and args.ra_sampler:
            train_sampler = RASampler(dataset, shuffle=True, repetitions=args.ra_reps)
        else:
            train_sampler = torch.utils.data.distributed.DistributedSampler(dataset)
        test_sampler = torch.utils.data.distributed.DistributedSampler(dataset_test, shuffle=False)
    else:
        train_sampler = torch.utils.data.RandomSampler(dataset)
        test_sampler = torch.utils.data.SequentialSampler(dataset_test)

    return dataset, dataset_test, train_sampler, test_sampler


def main(args,num):
    if args.output_dir:
        utils.mkdir(args.output_dir)

    utils.init_distributed_mode(args)
    print(args)
    
    device = torch.device('cuda', args.gpu)

    if args.use_deterministic_algorithms:
        torch.backends.cudnn.benchmark = False
        torch.use_deterministic_algorithms(True)
    else:
        torch.backends.cudnn.benchmark = True

    train_dir = os.path.join(args.data_path, "train")
    val_dir = os.path.join(args.data_path, "val")
    dataset, dataset_test, train_sampler, test_sampler = load_data(num, train_dir, val_dir, args)

    num_classes = 1000
    mixup_cutmix = get_mixup_cutmix(
        mixup_alpha=args.mixup_alpha, cutmix_alpha=args.cutmix_alpha, num_classes=num_classes, use_v2=args.use_v2
    )
    if mixup_cutmix is not None:

        def collate_fn(batch):
            return mixup_cutmix(*default_collate(batch))

    else:
        collate_fn = default_collate

    data_loader = torch.utils.data.DataLoader(
        dataset,
        batch_size=args.batch_size,
        sampler=train_sampler,
        num_workers=args.workers,
        pin_memory=True,
        collate_fn=collate_fn,
    )
    data_loader_test = torch.utils.data.DataLoader(
        dataset_test, batch_size=args.batch_size, sampler=test_sampler, num_workers=args.workers, pin_memory=True
    )

    print("Creating model")
    model = torchvision.models.get_model(args.model, weights=args.weights, num_classes=num_classes)
    model.to(device)
    
    if args.distributed and args.sync_bn:
        model = torch.nn.SyncBatchNorm.convert_sync_batchnorm(model)

    criterion = nn.CrossEntropyLoss(label_smoothing=args.label_smoothing)

    custom_keys_weight_decay = []
    if args.bias_weight_decay is not None:
        custom_keys_weight_decay.append(("bias", args.bias_weight_decay))
    if args.transformer_embedding_decay is not None:
        for key in ["class_token", "position_embedding", "relative_position_bias_table"]:
            custom_keys_weight_decay.append((key, args.transformer_embedding_decay))
    parameters = utils.set_weight_decay(
        model,
        args.weight_decay,
        norm_weight_decay=args.norm_weight_decay,
        custom_keys_weight_decay=custom_keys_weight_decay if len(custom_keys_weight_decay) > 0 else None,
    )

    opt_name = args.opt.lower()
    if opt_name.startswith("sgd"):
        optimizer = torch.optim.SGD(
            parameters,
            lr=args.lr,
            momentum=args.momentum,
            weight_decay=args.weight_decay,
            nesterov="nesterov" in opt_name,
        )
    elif opt_name == "rmsprop":
        optimizer = torch.optim.RMSprop(
            parameters, lr=args.lr, momentum=args.momentum, weight_decay=args.weight_decay, eps=0.0316, alpha=0.9
        )
    elif opt_name == "adamw":
        optimizer = torch.optim.AdamW(parameters, lr=args.lr, weight_decay=args.weight_decay)
    else:
        raise RuntimeError(f"Invalid optimizer {args.opt}. Only SGD, RMSprop and AdamW are supported.")

    scaler = torch.cuda.amp.GradScaler() if args.amp else None

    args.lr_scheduler = args.lr_scheduler.lower()
    if args.lr_scheduler == "steplr":
        main_lr_scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=args.lr_step_size, gamma=args.lr_gamma)
    elif args.lr_scheduler == "cosineannealinglr":
        main_lr_scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=args.epochs - args.lr_warmup_epochs, eta_min=args.lr_min
        )
    elif args.lr_scheduler == "exponentiallr":
        main_lr_scheduler = torch.optim.lr_scheduler.ExponentialLR(optimizer, gamma=args.lr_gamma)
    else:
        raise RuntimeError(
            f"Invalid lr scheduler '{args.lr_scheduler}'. Only StepLR, CosineAnnealingLR and ExponentialLR "
            "are supported."
        )

    if args.lr_warmup_epochs > 0:
        if args.lr_warmup_method == "linear":
            warmup_lr_scheduler = torch.optim.lr_scheduler.LinearLR(
                optimizer, start_factor=args.lr_warmup_decay, total_iters=args.lr_warmup_epochs
            )
        elif args.lr_warmup_method == "constant":
            warmup_lr_scheduler = torch.optim.lr_scheduler.ConstantLR(
                optimizer, factor=args.lr_warmup_decay, total_iters=args.lr_warmup_epochs
            )
        else:
            raise RuntimeError(
                f"Invalid warmup lr method '{args.lr_warmup_method}'. Only linear and constant are supported."
            )
        lr_scheduler = torch.optim.lr_scheduler.SequentialLR(
            optimizer, schedulers=[warmup_lr_scheduler, main_lr_scheduler], milestones=[args.lr_warmup_epochs]
        )
    else:
        lr_scheduler = main_lr_scheduler

    model_without_ddp = model
    if args.distributed:
        model = torch.nn.parallel.DistributedDataParallel(model, device_ids=[args.gpu])
        model_without_ddp = model.module

    model_ema = None
    if args.model_ema:
        adjust = args.world_size * args.batch_size * args.model_ema_steps / args.epochs
        alpha = 1.0 - args.model_ema_decay
        alpha = min(1.0, alpha * adjust)
        model_ema = utils.ExponentialMovingAverage(model_without_ddp, device=device, decay=1.0 - alpha)

    if args.resume:
        checkpoint = torch.load(args.resume, map_location="cpu", weights_only=True)
        model_without_ddp.load_state_dict(checkpoint["model"])
        if not args.test_only:
            optimizer.load_state_dict(checkpoint["optimizer"])
            lr_scheduler.load_state_dict(checkpoint["lr_scheduler"])
        args.start_epoch = checkpoint["epoch"] + 1
        if model_ema:
            model_ema.load_state_dict(checkpoint["model_ema"])
        if scaler:
            scaler.load_state_dict(checkpoint["scaler"])

    if args.test_only:
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        if model_ema:
            evaluate(model_ema, criterion, data_loader_test, device=device, log_suffix="EMA")
        else:
            evaluate(model, criterion, data_loader_test, device=device)
        return

    print("Start training")
    start_time = time.time()

    best_top1 = 0.0
    best_top5 = 0.0
    best_epoch = 0
    no_improvement_epochs = 0
    early_stop = False

    for epoch in range(args.start_epoch, args.epochs):
        if early_stop:
            print(f"Early stopping at epoch {epoch} as accuracy has stabilized")
            break
            
        if args.distributed:
            train_sampler.set_epoch(epoch)
        
        train_one_epoch(model, criterion, optimizer, data_loader, device, epoch, args, model_ema, scaler)
        lr_scheduler.step()
        
        current_top1, current_top5 = evaluate(model, criterion, data_loader_test, device=device)
        if model_ema:
            evaluate(model_ema, criterion, data_loader_test, device=device, log_suffix="EMA")

        if current_top1 > best_top1 + 0.001:
            best_top1 = current_top1
            best_top5 = current_top5
            best_epoch = epoch
            no_improvement_epochs = 0
        else:
            no_improvement_epochs += 1
        
        if no_improvement_epochs >= 5:
            early_stop = True

        if args.output_dir:
            checkpoint = {
                "model": model_without_ddp.state_dict(),
                "optimizer": optimizer.state_dict(),
                "lr_scheduler": lr_scheduler.state_dict(),
                "epoch": epoch,
                "args": args,
                "best_top1": best_top1,
                "best_top5": best_top5,
                "best_epoch": best_epoch
            }
            if model_ema:
                checkpoint["model_ema"] = model_ema.state_dict()
            if scaler:
                checkpoint["scaler"] = scaler.state_dict()
            
            utils.save_on_master(
                checkpoint,
                os.path.join(args.output_dir, f"model_{epoch}.pth"),
            )
            utils.save_on_master(
                checkpoint,
                os.path.join(args.output_dir, "checkpoint.pth"),
            )

    total_time = time.time() - start_time
    total_time_str = str(datetime.timedelta(seconds=int(total_time)))
    print(f"Training completed in {total_time_str}")
    print(f"Best validation - Epoch: {best_epoch}  Top1: {best_top1:.4f}  Top5: {best_top5:.4f}")

    return best_top1, best_top5


def get_args_parser(add_help=True):
    import argparse

    parser = argparse.ArgumentParser(description="PyTorch Classification Training", add_help=add_help)

    parser.add_argument("--data-path", default="/data1/simon-20372/imagenet", type=str, help="dataset path")
    parser.add_argument("--model", default="alexnet", type=str, help="model name")
    parser.add_argument("--device", default="cuda:0", type=str, help="device (Use cuda or cpu Default: cuda)")
    parser.add_argument(
        "-b", "--batch-size", default=32, type=int, help="images per gpu, the total batch size is $NGPU x batch_size"
    )
    parser.add_argument("--epochs", default=90, type=int, metavar="N", help="number of total epochs to run")
    parser.add_argument(
        "-j", "--workers", default=16, type=int, metavar="N", help="number of data loading workers (default: 16)"
    )
    parser.add_argument("--opt", default="sgd", type=str, help="optimizer")
    parser.add_argument("--lr", default=0.1, type=float, help="initial learning rate")
    parser.add_argument("--momentum", default=0.9, type=float, metavar="M", help="momentum")
    parser.add_argument(
        "--wd",
        "--weight-decay",
        default=1e-4,
        type=float,
        metavar="W",
        help="weight decay (default: 1e-4)",
        dest="weight_decay",
    )
    parser.add_argument(
        "--norm-weight-decay",
        default=None,
        type=float,
        help="weight decay for Normalization layers (default: None, same value as --wd)",
    )
    parser.add_argument(
        "--bias-weight-decay",
        default=None,
        type=float,
        help="weight decay for bias parameters of all layers (default: None, same value as --wd)",
    )
    parser.add_argument(
        "--transformer-embedding-decay",
        default=None,
        type=float,
        help="weight decay for embedding parameters for vision transformer models (default: None, same value as --wd)",
    )
    parser.add_argument(
        "--label-smoothing", default=0.0, type=float, help="label smoothing (default: 0.0)", dest="label_smoothing"
    )
    parser.add_argument("--mixup-alpha", default=0.0, type=float, help="mixup alpha (default: 0.0)")
    parser.add_argument("--cutmix-alpha", default=0.0, type=float, help="cutmix alpha (default: 0.0)")
    parser.add_argument("--lr-scheduler", default="steplr", type=str, help="the lr scheduler (default: steplr)")
    parser.add_argument("--lr-warmup-epochs", default=0, type=int, help="the number of epochs to warmup (default: 0)")
    parser.add_argument(
        "--lr-warmup-method", default="constant", type=str, help="the warmup method (default: constant)"
    )
    parser.add_argument("--lr-warmup-decay", default=0.01, type=float, help="the decay for lr")
    parser.add_argument("--lr-step-size", default=30, type=int, help="decrease lr every step-size epochs")
    parser.add_argument("--lr-gamma", default=0.1, type=float, help="decrease lr by a factor of lr-gamma")
    parser.add_argument("--lr-min", default=0.0, type=float, help="minimum lr of lr schedule (default: 0.0)")
    parser.add_argument("--print-freq", default=10, type=int, help="print frequency")
    parser.add_argument("--output-dir", default=".", type=str, help="path to save outputs")
    parser.add_argument("--resume", default="", type=str, help="path of checkpoint")
    parser.add_argument("--start-epoch", default=0, type=int, metavar="N", help="start epoch")
    parser.add_argument(
        "--cache-dataset",
        dest="cache_dataset",
        help="Cache the datasets for quicker initialization. It also serializes the transforms",
        action="store_true",
    )
    parser.add_argument(
        "--sync-bn",
        dest="sync_bn",
        help="Use sync batch norm",
        action="store_true",
    )
    parser.add_argument(
        "--test-only",
        dest="test_only",
        help="Only test the model",
        action="store_true",
    )
    parser.add_argument("--auto-augment", default=None, type=str, help="auto augment policy (default: None)")
    parser.add_argument("--ra-magnitude", default=9, type=int, help="magnitude of auto augment policy")
    parser.add_argument("--augmix-severity", default=3, type=int, help="severity of augmix policy")
    parser.add_argument("--random-erase", default=0.0, type=float, help="random erasing probability (default: 0.0)")

    # Mixed precision training parameters
    parser.add_argument("--amp", action="store_true", help="Use torch.cuda.amp for mixed precision training")

    # distributed training parameters
    parser.add_argument("--world-size", default=1, type=int, help="number of distributed processes")
    parser.add_argument("--dist-url", default="env://", type=str, help="url used to set up distributed training")
    parser.add_argument(
        "--model-ema", action="store_true", help="enable tracking Exponential Moving Average of model parameters"
    )
    parser.add_argument(
        "--model-ema-steps",
        type=int,
        default=32,
        help="the number of iterations that controls how often to update the EMA model (default: 32)",
    )
    parser.add_argument(
        "--model-ema-decay",
        type=float,
        default=0.99998,
        help="decay factor for Exponential Moving Average of model parameters (default: 0.99998)",
    )
    parser.add_argument(
        "--use-deterministic-algorithms", action="store_true", help="Forces the use of deterministic algorithms only."
    )
    parser.add_argument(
        "--interpolation", default="bilinear", type=str, help="the interpolation method (default: bilinear)"
    )
    parser.add_argument(
        "--val-resize-size", default=256, type=int, help="the resize size used for validation (default: 256)"
    )
    parser.add_argument(
        "--val-crop-size", default=224, type=int, help="the central crop size used for validation (default: 224)"
    )
    parser.add_argument(
        "--train-crop-size", default=224, type=int, help="the random crop size used for training (default: 224)"
    )
    parser.add_argument("--clip-grad-norm", default=None, type=float, help="the maximum gradient norm (default None)")
    parser.add_argument("--ra-sampler", action="store_true", help="whether to use Repeated Augmentation in training")
    parser.add_argument(
        "--ra-reps", default=3, type=int, help="number of repetitions for Repeated Augmentation (default: 3)"
    )
    parser.add_argument("--weights", default=None, type=str, help="the weights enum name to load")
    parser.add_argument("--backend", default="PIL", type=str.lower, help="PIL or tensor - case insensitive")
    parser.add_argument("--use-v2", action="store_true", help="Use V2 transforms")
    parser.add_argument("--num", default=1000, type=int, help="number of data to train")
    return parser


if __name__ == "__main__":
    model_param_mapping = {
        'alexnet': {'lr': 0.01},
        'vgg11': {'lr': 0.01},
        'vgg13': {'lr': 0.01},
        'vgg16': {'lr': 0.01},
        'vgg19': {'lr': 0.01},
        'vgg11_bn': {'lr': 0.01},
        'vgg13_bn': {'lr': 0.01},
        'vgg16_bn': {'lr': 0.01},
        'vgg19_bn': {'lr': 0.01},
        'resnext50_32x4d': {'epochs': 100},
        'resnext101_32x8d': {'epochs': 100},
        'mobilenet_v2': {'lr': 0.045, 'epochs': 300, 'weight_decay': 0.00004, 'lr_step_size': 1, 'lr_gamma': 0.98},
        'mobilenet_v3_large': {'epochs': 600, 'opt': 'rmsprop', 'batch_size': 128, 'lr': 0.064, 
                       'weight_decay': 0.00001, 'lr_step_size': 2, 'lr_gamma': 0.973, 
                       'auto_augment': 'imagenet', 'random_erase': 0.2},
        'mobilenet_v3_small': {'epochs': 600, 'opt': 'rmsprop', 'batch_size': 128, 'lr': 0.064, 
                       'weight_decay': 0.00001, 'lr_step_size': 2, 'lr_gamma': 0.973, 
                       'auto_augment': 'imagenet', 'random_erase': 0.2},
        'efficientnet_v2_s': {'epochs': 600, 'batch_size': 128, 'lr': 0.5, 'lr_scheduler': 'cosineannealinglr', 
                      'lr_warmup_epochs': 5, 'lr_warmup_method': 'linear', 'auto_augment': 'ta_wide', 
                      'random_erase': 0.1, 'label_smoothing': 0.1, 'mixup_alpha': 0.2, 'cutmix_alpha': 1.0, 
                      'weight_decay': 0.00002, 'norm_weight_decay': 0.0, 'train_crop_size': 300, 
                      'model_ema': True, 'val_crop_size': 384, 'val_resize_size': 384, 
                      'ra_sampler': True, 'ra_reps': 4},
        'efficientnet_v2_m': {'epochs': 600, 'batch_size': 128, 'lr': 0.5, 'lr_scheduler': 'cosineannealinglr', 
                      'lr_warmup_epochs': 5, 'lr_warmup_method': 'linear', 'auto_augment': 'ta_wide', 
                      'random_erase': 0.1, 'label_smoothing': 0.1, 'mixup_alpha': 0.2, 'cutmix_alpha': 1.0, 
                      'weight_decay': 0.00002, 'norm_weight_decay': 0.0, 'train_crop_size': 384, 
                      'model_ema': True, 'val_crop_size': 400, 'val_resize_size': 400, 
                      'ra_sampler': True, 'ra_reps': 4},
        'regnet_x_400mf': {'epochs': 100, 'batch_size': 128, 'weight_decay': 0.00005, 'lr': 0.8, 
                   'lr_scheduler': 'cosineannealinglr', 'lr_warmup_method': 'linear', 
                   'lr_warmup_epochs': 5, 'lr_warmup_decay': 0.1},
        'regnet_x_800mf': {'epochs': 100, 'batch_size': 128, 'weight_decay': 0.00005, 'lr': 0.8, 
                   'lr_scheduler': 'cosineannealinglr', 'lr_warmup_method': 'linear', 
                   'lr_warmup_epochs': 5, 'lr_warmup_decay': 0.1},
        'regnet_x_1_6gf': {'epochs': 100, 'batch_size': 128, 'weight_decay': 0.00005, 'lr': 0.8, 
                   'lr_scheduler': 'cosineannealinglr', 'lr_warmup_method': 'linear', 
                   'lr_warmup_epochs': 5, 'lr_warmup_decay': 0.1},
        'regnet_y_400mf': {'epochs': 100, 'batch_size': 128, 'weight_decay': 0.00005, 'lr': 0.8, 
                   'lr_scheduler': 'cosineannealinglr', 'lr_warmup_method': 'linear', 
                   'lr_warmup_epochs': 5, 'lr_warmup_decay': 0.1},
        'regnet_y_800mf': {'epochs': 100, 'batch_size': 128, 'weight_decay': 0.00005, 'lr': 0.8, 
                   'lr_scheduler': 'cosineannealinglr', 'lr_warmup_method': 'linear', 
                   'lr_warmup_epochs': 5, 'lr_warmup_decay': 0.1},
        'regnet_y_1_6gf': {'epochs': 100, 'batch_size': 128, 'weight_decay': 0.00005, 'lr': 0.8, 
                   'lr_scheduler': 'cosineannealinglr', 'lr_warmup_method': 'linear', 
                   'lr_warmup_epochs': 5, 'lr_warmup_decay': 0.1},
        'regnet_x_3_2gf': {'epochs': 100, 'batch_size': 64, 'weight_decay': 0.00005, 'lr': 0.4, 
               'lr_scheduler': 'cosineannealinglr', 'lr_warmup_method': 'linear', 
               'lr_warmup_epochs': 5, 'lr_warmup_decay': 0.1},
        'regnet_x_8gf': {'epochs': 100, 'batch_size': 64, 'weight_decay': 0.00005, 'lr': 0.4, 
               'lr_scheduler': 'cosineannealinglr', 'lr_warmup_method': 'linear', 
               'lr_warmup_epochs': 5, 'lr_warmup_decay': 0.1},
        'regnet_x_16gf': {'epochs': 100, 'batch_size': 64, 'weight_decay': 0.00005, 'lr': 0.4, 
               'lr_scheduler': 'cosineannealinglr', 'lr_warmup_method': 'linear', 
               'lr_warmup_epochs': 5, 'lr_warmup_decay': 0.1},
        'regnet_y_3_2gf': {'epochs': 100, 'batch_size': 64, 'weight_decay': 0.00005, 'lr': 0.4, 
               'lr_scheduler': 'cosineannealinglr', 'lr_warmup_method': 'linear', 
               'lr_warmup_epochs': 5, 'lr_warmup_decay': 0.1},
        'regnet_y_8gf': {'epochs': 100, 'batch_size': 64, 'weight_decay': 0.00005, 'lr': 0.4, 
               'lr_scheduler': 'cosineannealinglr', 'lr_warmup_method': 'linear', 
               'lr_warmup_epochs': 5, 'lr_warmup_decay': 0.1},
        'regnet_x_32gf': {'epochs': 100, 'batch_size': 64, 'weight_decay': 0.00005, 'lr': 0.4, 
               'lr_scheduler': 'cosineannealinglr', 'lr_warmup_method': 'linear', 
               'lr_warmup_epochs': 5, 'lr_warmup_decay': 0.1},
        'regnet_y_16gf': {'epochs': 100, 'batch_size': 64, 'weight_decay': 0.00005, 'lr': 0.4, 
               'lr_scheduler': 'cosineannealinglr', 'lr_warmup_method': 'linear', 
               'lr_warmup_epochs': 5, 'lr_warmup_decay': 0.1},
        'regnet_y_32gf': {'epochs': 100, 'batch_size': 64, 'weight_decay': 0.00005, 'lr': 0.4, 
               'lr_scheduler': 'cosineannealinglr', 'lr_warmup_method': 'linear', 
               'lr_warmup_epochs': 5, 'lr_warmup_decay': 0.1},
        'vit_b_16': {'epochs': 300, 'batch_size': 512, 'opt': 'adamw', 'lr': 0.003, 
                 'weight_decay': 0.3, 'lr_scheduler': 'cosineannealinglr', 
                 'lr_warmup_method': 'linear', 'lr_warmup_epochs': 30, 
                 'lr_warmup_decay': 0.033, 'amp': True, 'label_smoothing': 0.11, 
                 'mixup_alpha': 0.2, 'auto_augment': 'ra', 'clip_grad_norm': 1, 
                 'ra_sampler': True, 'cutmix_alpha': 1.0, 'model_ema': True},
        'vit_b_32': {'epochs': 300, 'batch_size': 512, 'opt': 'adamw', 'lr': 0.003, 
             'weight_decay': 0.3, 'lr_scheduler': 'cosineannealinglr', 
             'lr_warmup_method': 'linear', 'lr_warmup_epochs': 30, 
             'lr_warmup_decay': 0.033, 'amp': True, 'label_smoothing': 0.11, 
             'mixup_alpha': 0.2, 'auto_augment': 'imagenet', 'clip_grad_norm': 1, 
             'ra_sampler': True, 'cutmix_alpha': 1.0, 'model_ema': True},
        'vit_l_16': {'epochs': 600, 'batch_size': 128, 'opt': 'adamw', 'lr': 0.5, 
             'weight_decay': 0.00002, 'lr_scheduler': 'cosineannealinglr', 
             'lr_warmup_method': 'linear', 'lr_warmup_epochs': 5, 
             'label_smoothing': 0.1, 'mixup_alpha': 0.2, 'auto_augment': 'ta_wide', 
             'random_erase': 0.1, 'clip_grad_norm': 1, 'ra_sampler': True, 
             'cutmix_alpha': 1.0, 'model_ema': True, 'val_resize_size': 232, 
             'norm_weight_decay': 0.0},
        'vit_l_32': {'epochs': 300, 'batch_size': 512, 'opt': 'adamw', 'lr': 0.003, 
             'weight_decay': 0.3, 'lr_scheduler': 'cosineannealinglr', 
             'lr_warmup_method': 'linear', 'lr_warmup_epochs': 30, 
             'lr_warmup_decay': 0.033, 'amp': True, 'label_smoothing': 0.11, 
             'mixup_alpha': 0.2, 'auto_augment': 'ra', 'clip_grad_norm': 1, 
             'ra_sampler': True, 'cutmix_alpha': 1.0, 'model_ema': True},
        'convnext_tiny': {'epochs': 600, 'batch_size': 128, 'opt': 'adamw', 'lr': 1e-3, 
                  'lr_scheduler': 'cosineannealinglr', 'lr_warmup_epochs': 5, 
                  'lr_warmup_method': 'linear', 'auto_augment': 'ta_wide', 
                  'random_erase': 0.1, 'label_smoothing': 0.1, 'mixup_alpha': 0.2, 
                  'cutmix_alpha': 1.0, 'weight_decay': 0.05, 'norm_weight_decay': 0.0, 
                  'train_crop_size': 176, 'model_ema': True, 'val_resize_size': 232, 
                  'ra_sampler': True, 'ra_reps': 4},
        'convnext_small': {'epochs': 600, 'batch_size': 128, 'opt': 'adamw', 'lr': 1e-3, 
                   'lr_scheduler': 'cosineannealinglr', 'lr_warmup_epochs': 5, 
                   'lr_warmup_method': 'linear', 'auto_augment': 'ta_wide', 
                   'random_erase': 0.1, 'label_smoothing': 0.1, 'mixup_alpha': 0.2, 
                   'cutmix_alpha': 1.0, 'weight_decay': 0.05, 'norm_weight_decay': 0.0, 
                   'train_crop_size': 176, 'model_ema': True, 'val_resize_size': 232, 
                   'ra_sampler': True, 'ra_reps': 4},
        'convnext_base': {'epochs': 600, 'batch_size': 128, 'opt': 'adamw', 'lr': 1e-3, 
                  'lr_scheduler': 'cosineannealinglr', 'lr_warmup_epochs': 5, 
                  'lr_warmup_method': 'linear', 'auto_augment': 'ta_wide', 
                  'random_erase': 0.1, 'label_smoothing': 0.1, 'mixup_alpha': 0.2, 
                  'cutmix_alpha': 1.0, 'weight_decay': 0.05, 'norm_weight_decay': 0.0, 
                  'train_crop_size': 176, 'model_ema': True, 'val_resize_size': 232, 
                  'ra_sampler': True, 'ra_reps': 4},
        'convnext_large': {'epochs': 600, 'batch_size': 128, 'opt': 'adamw', 'lr': 1e-3, 
                   'lr_scheduler': 'cosineannealinglr', 'lr_warmup_epochs': 5, 
                   'lr_warmup_method': 'linear', 'auto_augment': 'ta_wide', 
                   'random_erase': 0.1, 'label_smoothing': 0.1, 'mixup_alpha': 0.2, 
                   'cutmix_alpha': 1.0, 'weight_decay': 0.05, 'norm_weight_decay': 0.0, 
                   'train_crop_size': 176, 'model_ema': True, 'val_resize_size': 232, 
                   'ra_sampler': True, 'ra_reps': 4},
        'swin_t': {'epochs': 300, 'batch_size': 128, 'opt': 'adamw', 'lr': 0.001, 
               'weight_decay': 0.05, 'norm_weight_decay': 0.0, 'bias_weight_decay': 0.0, 
               'transformer_embedding_decay': 0.0, 'lr_scheduler': 'cosineannealinglr', 
               'lr_min': 0.00001, 'lr_warmup_method': 'linear', 'lr_warmup_epochs': 20, 
               'lr_warmup_decay': 0.01, 'amp': True, 'label_smoothing': 0.1, 
               'mixup_alpha': 0.8, 'clip_grad_norm': 5.0, 'cutmix_alpha': 1.0, 
               'random_erase': 0.25, 'interpolation': 'bicubic', 'auto_augment': 'ta_wide', 
               'model_ema': True, 'ra_sampler': True, 'ra_reps': 4, 'val_resize_size': 224},
        'swin_s': {'epochs': 300, 'batch_size': 128, 'opt': 'adamw', 'lr': 0.001, 
               'weight_decay': 0.05, 'norm_weight_decay': 0.0, 'bias_weight_decay': 0.0, 
               'transformer_embedding_decay': 0.0, 'lr_scheduler': 'cosineannealinglr', 
               'lr_min': 0.00001, 'lr_warmup_method': 'linear', 'lr_warmup_epochs': 20, 
               'lr_warmup_decay': 0.01, 'amp': True, 'label_smoothing': 0.1, 
               'mixup_alpha': 0.8, 'clip_grad_norm': 5.0, 'cutmix_alpha': 1.0, 
               'random_erase': 0.25, 'interpolation': 'bicubic', 'auto_augment': 'ta_wide', 
               'model_ema': True, 'ra_sampler': True, 'ra_reps': 4, 'val_resize_size': 224},
        'swin_b': {'epochs': 300, 'batch_size': 128, 'opt': 'adamw', 'lr': 0.001, 
               'weight_decay': 0.05, 'norm_weight_decay': 0.0, 'bias_weight_decay': 0.0, 
               'transformer_embedding_decay': 0.0, 'lr_scheduler': 'cosineannealinglr', 
               'lr_min': 0.00001, 'lr_warmup_method': 'linear', 'lr_warmup_epochs': 20, 
               'lr_warmup_decay': 0.01, 'amp': True, 'label_smoothing': 0.1, 
               'mixup_alpha': 0.8, 'clip_grad_norm': 5.0, 'cutmix_alpha': 1.0, 
               'random_erase': 0.25, 'interpolation': 'bicubic', 'auto_augment': 'ta_wide', 
               'model_ema': True, 'ra_sampler': True, 'ra_reps': 4, 'val_resize_size': 224},
        'swin_v2_t': {'epochs': 300, 'batch_size': 128, 'opt': 'adamw', 'lr': 0.001, 
                  'weight_decay': 0.05, 'norm_weight_decay': 0.0, 'bias_weight_decay': 0.0, 
                  'transformer_embedding_decay': 0.0, 'lr_scheduler': 'cosineannealinglr', 
                  'lr_min': 0.00001, 'lr_warmup_method': 'linear', 'lr_warmup_epochs': 20, 
                  'lr_warmup_decay': 0.01, 'amp': True, 'label_smoothing': 0.1, 
                  'mixup_alpha': 0.8, 'clip_grad_norm': 5.0, 'cutmix_alpha': 1.0, 
                  'random_erase': 0.25, 'interpolation': 'bicubic', 'auto_augment': 'ta_wide', 
                  'model_ema': True, 'ra_sampler': True, 'ra_reps': 4, 'val_resize_size': 256, 
                  'val_crop_size': 256, 'train_crop_size': 256},
        'swin_v2_s': {'epochs': 300, 'batch_size': 128, 'opt': 'adamw', 'lr': 0.001, 
                  'weight_decay': 0.05, 'norm_weight_decay': 0.0, 'bias_weight_decay': 0.0, 
                  'transformer_embedding_decay': 0.0, 'lr_scheduler': 'cosineannealinglr', 
                  'lr_min': 0.00001, 'lr_warmup_method': 'linear', 'lr_warmup_epochs': 20, 
                  'lr_warmup_decay': 0.01, 'amp': True, 'label_smoothing': 0.1, 
                  'mixup_alpha': 0.8, 'clip_grad_norm': 5.0, 'cutmix_alpha': 1.0, 
                  'random_erase': 0.25, 'interpolation': 'bicubic', 'auto_augment': 'ta_wide', 
                  'model_ema': True, 'ra_sampler': True, 'ra_reps': 4, 'val_resize_size': 256, 
                  'val_crop_size': 256, 'train_crop_size': 256},
        'swin_v2_b': {'epochs': 300, 'batch_size': 128, 'opt': 'adamw', 'lr': 0.001, 
                  'weight_decay': 0.05, 'norm_weight_decay': 0.0, 'bias_weight_decay': 0.0, 
                  'transformer_embedding_decay': 0.0, 'lr_scheduler': 'cosineannealinglr', 
                  'lr_min': 0.00001, 'lr_warmup_method': 'linear', 'lr_warmup_epochs': 20, 
                  'lr_warmup_decay': 0.01, 'amp': True, 'label_smoothing': 0.1, 
                  'mixup_alpha': 0.8, 'clip_grad_norm': 5.0, 'cutmix_alpha': 1.0, 
                  'random_erase': 0.25, 'interpolation': 'bicubic', 'auto_augment': 'ta_wide', 
                  'model_ema': True, 'ra_sampler': True, 'ra_reps': 4, 'val_resize_size': 256, 
                  'val_crop_size': 256, 'train_crop_size': 256},
        'maxvit_t': {'epochs': 400, 'batch_size': 128, 'opt': 'adamw', 'lr': 3e-3, 
                 'weight_decay': 0.05, 'lr_scheduler': 'cosineannealinglr', 
                 'lr_min': 1e-5, 'lr_warmup_method': 'linear', 'lr_warmup_epochs': 32, 
                 'label_smoothing': 0.1, 'mixup_alpha': 0.8, 'clip_grad_norm': 1.0, 
                 'interpolation': 'bicubic', 'auto_augment': 'ta_wide', 
                 'policy_magnitude': 15, 'model_ema': True, 'val_resize_size': 224, 
                 'val_crop_size': 224, 'train_crop_size': 224, 'amp': True, 
                 'model_ema_steps': 32, 'transformer_embedding_decay': 0, 'sync_bn': True},
        'shufflenet_v2_x1_5': {'batch_size': 128, 'lr': 0.5, 'lr_scheduler': 'cosineannealinglr', 
                       'lr_warmup_epochs': 5, 'lr_warmup_method': 'linear', 'auto_augment': 'ta_wide', 
                       'epochs': 600, 'random_erase': 0.1, 'weight_decay': 0.00002, 
                       'norm_weight_decay': 0.0, 'label_smoothing': 0.1, 'mixup_alpha': 0.2, 
                       'cutmix_alpha': 1.0, 'train_crop_size': 176, 'model_ema': True, 
                       'val_resize_size': 232, 'ra_sampler': True, 'ra_reps': 4},
        'shufflenet_v2_x2_0': {'batch_size': 128, 'lr': 0.5, 'lr_scheduler': 'cosineannealinglr', 
                       'lr_warmup_epochs': 5, 'lr_warmup_method': 'linear', 'auto_augment': 'ta_wide', 
                       'epochs': 600, 'random_erase': 0.1, 'weight_decay': 0.00002, 
                       'norm_weight_decay': 0.0, 'label_smoothing': 0.1, 'mixup_alpha': 0.2, 
                       'cutmix_alpha': 1.0, 'train_crop_size': 176, 'model_ema': True, 
                       'val_resize_size': 232, 'ra_sampler': True, 'ra_reps': 4}
    }
    

    parser = get_args_parser()
    parser.add_argument('--distributed', action='store_true', default=True, help='use distributed training')
    args = parser.parse_args()

    if args.model in model_param_mapping:
        for key, value in model_param_mapping[args.model].items():
            setattr(args, key, value)
            
    if not args.distributed and hasattr(args, 'batch_size'):
        setattr(args, 'batch_size', args.batch_size * 8)

    result_file = f'./result/{args.model}.csv'
    
    if not os.path.exists(result_file):
        pd.DataFrame(columns=['Num', 'Top-1 Accuracy', 'Top-5 Accuracy']).to_csv(result_file, index=False)
    
    torch.cuda.empty_cache()
    top1_accuracy, top5_accuracy = main(args, args.num)
    result = (args.num, top1_accuracy, top5_accuracy)
    if not torch.distributed.is_initialized() or torch.distributed.get_rank() == 0:
        df = pd.DataFrame([result], columns=["Num", "Top-1 Accuracy", "Top-5 Accuracy"])
        df.to_csv(result_file, mode='a', header=False, index=False)
