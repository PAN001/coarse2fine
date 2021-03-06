from __future__ import division
import os
import argparse
import torch
import codecs
import glob

import table
import table.IO
import opts
import table.modules.bleu_score
from nltk.translate.bleu_score import corpus_bleu, SmoothingFunction

parser = argparse.ArgumentParser(description='evaluate.py')
opts.translate_opts(parser)
opt = parser.parse_args()
torch.cuda.set_device(opt.gpu)
opt.anno = os.path.join(opt.root_dir, opt.dataset, '{}.json'.format(opt.split))
opt.pre_word_vecs = os.path.join(opt.root_dir, opt.dataset, 'embedding')

if opt.beam_size > 0:
    opt.batch_size = 1


def main():
    dummy_parser = argparse.ArgumentParser(description='train.py')
    opts.model_opts(dummy_parser)
    opts.train_opts(dummy_parser)
    dummy_opt = dummy_parser.parse_known_args([])[0]

    js_list = table.IO.read_anno_json(opt.anno, opt)

    metric_name_list = ['tgt']
    prev_best = (None, None)
    for fn_model in glob.glob(opt.model_path):
        opt.model = fn_model
        print(fn_model)
        print(opt.anno)

        translator = table.Translator(opt, dummy_opt.__dict__)
        data = table.IO.TableDataset(
            js_list, translator.fields, 0, None, False)
        test_data = table.IO.OrderedIterator(
            dataset=data, device=opt.gpu, batch_size=opt.batch_size, train=False, sort=True, sort_within_batch=False)

        # inference
        r_list = []
        for batch in test_data:
            r = translator.translate(batch)
            r_list += r
        r_list.sort(key=lambda x: x.idx)
        assert len(r_list) == len(js_list), 'len(r_list) != len(js_list): {} != {}'.format(
            len(r_list), len(js_list))

        # evaluation
        for pred, gold in zip(r_list, js_list):
            print("pred tgt: ", pred.tgt)
            print("pred lay: ", pred.lay)
            print("gold:", gold)

            pred.eval(gold)
        print('Results:')
        for metric_name in metric_name_list:
            c_correct = sum((x.correct[metric_name] for x in r_list))
            acc = c_correct / len(r_list)
            print('{}: {} / {} = {:.2%}'.format(metric_name,
                                                c_correct, len(r_list), acc))
            if metric_name == 'tgt' and (prev_best[0] is None or acc > prev_best[1]):
                prev_best = (fn_model, acc)

        # calcualte bleu score
        pred_tgt_tokens = [pred.tgt for pred in r_list]
        gold_tgt_tokens = [gold['tgt'] for gold in js_list]
        # print('pred_tgt_tokens[0]', pred_tgt_tokens[0])
        # print('gold_tgt_tokens[0]', gold_tgt_tokens[0])
        bleu_score = table.modules.bleu_score.compute_bleu(gold_tgt_tokens, pred_tgt_tokens, smooth=False)
        bleu_score = bleu_score[0]

        bleu_score_nltk = corpus_bleu(gold_tgt_tokens, pred_tgt_tokens, smoothing_function = SmoothingFunction().method3)


        print('{}: = {:.4}'.format('tgt blue score',
                                    bleu_score))

        print('{}: = {:.4}'.format('tgt nltk blue score',
                                    bleu_score_nltk))

    if (opt.split == 'dev') and (prev_best[0] is not None):
        with codecs.open(os.path.join(opt.root_dir, opt.dataset, 'dev_best.txt'), 'w', encoding='utf-8') as f_out:
            f_out.write('{}\n'.format(prev_best[0]))


if __name__ == "__main__":
    main()
